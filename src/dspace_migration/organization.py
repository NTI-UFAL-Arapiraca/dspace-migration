import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from dspace_rest_client.client import DSpaceClient

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMMUNITIES_FILE = PROJECT_ROOT / "dspace-organization" / "communities.json"
MAPPING_FILE = PROJECT_ROOT / "dspace-organization" / "map.json"


def load_community_structure(path: Path) -> dict:
    """Lê e retorna a estrutura da árvore de comunidades."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_curso_mapping(path: Path) -> dict[str, dict]:
    """
    Lê o arquivo map.json e retorna o mapeamento.
    Formato: {old_name: {"new_collection_name": ..., "new_path": ...}}
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {item["old_name"]: item for item in data}


def parse_path(path_str: str) -> list[str]:
    """Divide a string de caminho em uma lista de componentes."""
    return [part.strip() for part in path_str.split(">")]


def resolve_collection_for_curso(curso_name: str | None, mapping: dict) -> str | None:
    """
    Dado o nome de um curso do banco antigo, retorna o 'new_path'
    string do mapping, ou None se não encontrado.
    """
    if curso_name and curso_name in mapping:
        return mapping[curso_name]["new_path"]
    return None


def get_saf_subpath(path_str: str) -> Path:
    """
    Converte uma string de caminho para um caminho relativo amigável ao sistema
    de arquivos. Pula a comunidade raiz (por exemplo, "Polo / Campus").
    """
    parts = parse_path(path_str)
    if len(parts) > 1:
        # Pula o nó raiz
        return Path(*parts[1:])
    return Path(parts[-1] if parts else "")


def ensure_hierarchy(api_url, user, password, community_tree) -> dict[str, str]:
    """
    Conecta na API REST do DSpace e garante que a hierarquia de comunidades e coleções exista.
    Retorna um dicionário {full_path_str: uuid} para as coleções criadas/existentes.
    """
    client = DSpaceClient(api_endpoint=api_url, username=user, password=password)
    client.authenticate()
    logger.info("Autenticado com sucesso na API REST do DSpace.")

    collection_uuids = {}

    def get_or_create_community(name: str, parent_uuid: str = None) -> str:
        if parent_uuid is None:
            existing = client.get_communities(top=True)
        else:
            url = f"{api_url}/core/communities/{parent_uuid}/subcommunities"
            r_json = client.fetch_resource(url)
            existing = []
            if r_json and "_embedded" in r_json and "subcommunities" in r_json["_embedded"]:
                from dspace_rest_client.models import Community
                for c_res in r_json["_embedded"]["subcommunities"]:
                    existing.append(Community(c_res))

        for comm in existing:
            if comm.name == name:
                logger.info(f"Comunidade '{name}' já existe ({comm.uuid}).")
                return comm.uuid

        logger.info(f"Criando comunidade '{name}'...")
        data = {"name": name, "metadata": {"dc.title": [{"value": name}]}}
        new_comm = client.create_community(parent_uuid, data)
        return new_comm.uuid

    def get_or_create_collection(name: str, community_uuid: str) -> str:
        url = f"{api_url}/core/communities/{community_uuid}/collections"
        r_json = client.fetch_resource(url)
        existing = []
        if r_json and "_embedded" in r_json and "collections" in r_json["_embedded"]:
            from dspace_rest_client.models import Collection
            for c_res in r_json["_embedded"]["collections"]:
                existing.append(Collection(c_res))

        for coll in existing:
            if coll.name == name:
                logger.info(f"Coleção '{name}' já existe ({coll.uuid}).")
                return coll.uuid

        logger.info(f"Criando coleção '{name}'...")
        data = {"name": name, "metadata": {"dc.title": [{"value": name}]}}
        new_coll = client.create_collection(community_uuid, data)
        return new_coll.uuid

    def walk(node: dict, parent_uuid: str, current_path: list[str]):
        name = node["name"]
        node_path = current_path + [name]
        node_path_str = " > ".join(node_path)

        if node.get("type") == "community":
            comm_uuid = get_or_create_community(name, parent_uuid)

            # Processar subcomunidades
            for sub in node.get("subcommunities", []):
                walk(sub, comm_uuid, node_path)

            # Processar coleções
            for coll in node.get("collections", []):
                coll_name = coll["name"]
                coll_path = node_path + [coll_name]
                coll_path_str = " > ".join(coll_path)

                coll_uuid = get_or_create_collection(coll_name, comm_uuid)
                collection_uuids[coll_path_str] = coll_uuid

    # Iniciar navegação recursiva
    walk(community_tree, None, [])
    return collection_uuids


def setup_dspace() -> dict[str, str]:
    """
    Ponto de entrada para configurar a hierarquia no DSpace, salvando o mapeamento
    de UUIDs resultante.
    """
    load_dotenv()
    api_url = os.getenv("DSPACE_API_URL", "http://localhost:8080/server/api")
    user = os.getenv("DSPACE_API_USER", "test@test.edu")
    password = os.getenv("DSPACE_API_PASSWORD", "admin")

    logger.info("Carregando estrutura das comunidades de: %s", COMMUNITIES_FILE)
    try:
        community_tree = load_community_structure(COMMUNITIES_FILE)
    except Exception as e:
        logger.error(f"Erro ao ler arquivo de comunidades: {e}")
        return {}

    logger.info("Assegurando hierarquia de comunidades/coleções...")
    try:
        collection_uuids = ensure_hierarchy(api_url, user, password, community_tree)
    except Exception as e:
        logger.error(f"Falha ao conectar/interagir com DSpace: {e}")
        return {}

    # Salvar resultados
    with open("collection_uuids.json", "w", encoding="utf-8") as f:
        json.dump(collection_uuids, f, ensure_ascii=False, indent=2)

    logger.info("Coleções processadas e UUIDs salvos em collection_uuids.json.")
    return collection_uuids


def generate_import_script(dspace_user: str = None) -> None:
    """
    Lê a configuração de coleções e os pacotes SAF e gera o script de importação.
    """
    load_dotenv()
    user = dspace_user or os.getenv("DSPACE_API_USER", "test@test.edu")

    try:
        with open("collection_uuids.json", "r", encoding="utf-8") as f:
            collection_uuids = json.load(f)
    except FileNotFoundError:
        logger.error("collection_uuids.json não encontrado. Execute setup_dspace() antes.")
        return
    except Exception as e:
        logger.error(f"Erro ao ler collection_uuids.json: {e}")
        return

    saf_bundle_dir_env = os.getenv("SAF_BUNDLE_DIR", "saf_bundle")
    saf_bundle_path = Path(saf_bundle_dir_env)

    script_lines = [
        "#!/bin/bash",
        "set -e"
    ]

    logger.info("Gerando script de importação (import_all.sh)...")

    for path_str, uuid in collection_uuids.items():
        subpath = get_saf_subpath(path_str)
        collection_dir = saf_bundle_path / subpath

        if collection_dir.is_dir():
            has_items = any(p.is_dir() and p.name.startswith("item_") for p in collection_dir.iterdir())
            if has_items:
                container_saf_path = f"/dspace/saf_bundle/{subpath.as_posix()}"
                cmd = f'/dspace/bin/dspace import -a -e {user} -c {uuid} -s "{container_saf_path}" -m "{container_saf_path}/mapfile.txt"'
                script_lines.append(cmd)
                logger.info(f"Incluído no script de importação: '{path_str}'")
            else:
                logger.warning(f"Aviso: Diretório da coleção '{path_str}' não contém pastas de itens ('item_*').")
        else:
            logger.warning(f"Aviso: Diretório de SAF da coleção '{path_str}' ({collection_dir}) não foi encontrado.")

    with open("import_all.sh", "w", encoding="utf-8") as f:
        f.write("\n".join(script_lines) + "\n")

    try:
        os.chmod("import_all.sh", 0o755)
    except OSError:
        pass

    logger.info("Script import_all.sh gerado com sucesso.")
