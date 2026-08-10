import json
import logging
import os
import shlex
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
    if not isinstance(data, list):
        raise ValueError(f"O arquivo de mapeamento deve conter uma lista: {path}")

    mapping = {}
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict) or not item.get("old_name") or not item.get("new_path"):
            raise ValueError(f"Entrada inválida no mapeamento {path}, posição {index}")
        old_name = item["old_name"]
        if old_name in mapping:
            raise ValueError(f"Curso duplicado no mapeamento {path}: {old_name}")
        mapping[old_name] = item
    return mapping


def parse_path(path_str: str) -> list[str]:
    """Divide a string de caminho em uma lista de componentes."""
    parts = [part.strip() for part in path_str.split(">")]
    if not parts or any(not part for part in parts):
        raise ValueError(f"Caminho de coleção inválido: {path_str!r}")
    return parts


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
    relative_parts = parts[1:] if len(parts) > 1 else parts
    if any(
        part in {".", ".."} or "/" in part or "\\" in part
        for part in relative_parts
    ):
        raise ValueError(f"Caminho SAF inseguro ou inválido: {path_str!r}")
    return Path(*relative_parts)


def _fetch_paginated_models(client, url, embedded_name, model_class) -> list:
    """Busca todos os recursos HAL, seguindo os links de paginação."""
    resources = []
    params = {"size": 100}
    while url:
        response = client.fetch_resource(url, params=params)
        if response is None:
            raise RuntimeError(f"Resposta vazia da API do DSpace: {url}")
        embedded = response.get("_embedded", {}).get(embedded_name, [])
        resources.extend(model_class(resource) for resource in embedded)
        url = response.get("_links", {}).get("next", {}).get("href")
        params = None
    return resources


def ensure_hierarchy(api_url, user, password, community_tree) -> dict[str, str]:
    """
    Conecta na API REST do DSpace e garante que a hierarquia de comunidades e coleções exista.
    Retorna um dicionário {full_path_str: uuid} para as coleções criadas/existentes.
    """
    client = DSpaceClient(api_endpoint=api_url, username=user, password=password)
    if not client.authenticate():
        raise RuntimeError("Falha na autenticação com a API REST do DSpace")
    logger.info("Autenticado com sucesso na API REST do DSpace.")

    collection_uuids = {}

    def get_or_create_community(name: str, parent_uuid: str = None) -> str:
        if parent_uuid is None:
            existing = list(client.get_communities_iter(top=True))
        else:
            from dspace_rest_client.models import Community

            url = f"{api_url}/core/communities/{parent_uuid}/subcommunities"
            existing = _fetch_paginated_models(
                client, url, "subcommunities", Community
            )

        for comm in existing:
            if comm.name == name:
                logger.info(f"Comunidade '{name}' já existe ({comm.uuid}).")
                return comm.uuid

        logger.info(f"Criando comunidade '{name}'...")
        data = {"name": name, "metadata": {"dc.title": [{"value": name}]}}
        new_comm = client.create_community(parent_uuid, data)
        if new_comm is None or not new_comm.uuid:
            raise RuntimeError(f"A API não criou a comunidade: {name}")
        return new_comm.uuid

    def get_or_create_collection(name: str, community_uuid: str) -> str:
        from dspace_rest_client.models import Collection

        url = f"{api_url}/core/communities/{community_uuid}/collections"
        existing = _fetch_paginated_models(client, url, "collections", Collection)

        for coll in existing:
            if coll.name == name:
                logger.info(f"Coleção '{name}' já existe ({coll.uuid}).")
                return coll.uuid

        logger.info(f"Criando coleção '{name}'...")
        data = {"name": name, "metadata": {"dc.title": [{"value": name}]}}
        new_coll = client.create_collection(community_uuid, data)
        if new_coll is None or not new_coll.uuid:
            raise RuntimeError(f"A API não criou a coleção: {name}")
        return new_coll.uuid

    def walk(node: dict, parent_uuid: str, current_path: list[str]):
        name = node["name"]
        node_path = current_path + [name]
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


def generate_import_script(
    dspace_user: str | None = None,
    *,
    collection_uuids_file: str | Path = "collection_uuids.json",
    saf_bundle_dir: str | Path | None = None,
    output_file: str | Path = "import_all.sh",
    container_saf_root: str = "/dspace/saf_bundle",
) -> int:
    """
    Lê a configuração de coleções e os pacotes SAF e gera o script de importação.
    """
    load_dotenv()
    user = dspace_user or os.getenv("DSPACE_API_USER", "test@test.edu")

    try:
        with open(collection_uuids_file, "r", encoding="utf-8") as f:
            collection_uuids = json.load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"{collection_uuids_file} não encontrado. Execute setup-dspace antes."
        ) from exc
    if not isinstance(collection_uuids, dict) or not collection_uuids:
        raise ValueError(f"Mapeamento de coleções vazio ou inválido: {collection_uuids_file}")

    saf_bundle_path = Path(
        saf_bundle_dir or os.getenv("SAF_BUNDLE_DIR", "saf_bundle")
    )

    script_lines = [
        "#!/bin/bash",
        "set -e"
    ]

    logger.info("Gerando script de importação (import_all.sh)...")
    import_count = 0

    for path_str, uuid in collection_uuids.items():
        subpath = get_saf_subpath(path_str)
        collection_dir = saf_bundle_path / subpath

        if collection_dir.is_dir():
            has_items = any(p.is_dir() and p.name.startswith("item_") for p in collection_dir.iterdir())
            if has_items:
                container_saf_path = (
                    f"{container_saf_root.rstrip('/')}/{subpath.as_posix()}"
                )
                cmd = " ".join([
                    "/dspace/bin/dspace import -a",
                    "-e", shlex.quote(user),
                    "-c", shlex.quote(str(uuid)),
                    "-s", shlex.quote(container_saf_path),
                    "-m", shlex.quote(f"{container_saf_path}/mapfile.txt"),
                ])
                script_lines.append(cmd)
                import_count += 1
                logger.info(f"Incluído no script de importação: '{path_str}'")
            else:
                logger.warning(f"Aviso: Diretório da coleção '{path_str}' não contém pastas de itens ('item_*').")
        else:
            logger.warning(f"Aviso: Diretório de SAF da coleção '{path_str}' ({collection_dir}) não foi encontrado.")

    if import_count == 0:
        raise RuntimeError(
            f"Nenhuma coleção com itens foi encontrada em {saf_bundle_path}"
        )

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(script_lines) + "\n")

    try:
        os.chmod(output_file, 0o755)
    except OSError:
        pass

    logger.info("Script %s gerado com %d comando(s).", output_file, import_count)
    return import_count
