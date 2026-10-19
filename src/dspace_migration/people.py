"""Migra pessoas bibliográficas sem criar contas EPerson."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from dspace_rest_client.client import DSpaceClient

from dspace_migration.statistics import read_mapfiles


PERSON_FIELDS = (
    "dc.contributor.author", "dc.contributor.advisor",
    "dc.contributor.coadvisor", "dc.contributor.referee",
)
SOURCE_TABLES = {
    "dc.contributor.author": "ud_biblioteca_publicacao_autor",
    **{field: "ud_biblioteca_publicacao_orientador" for field in PERSON_FIELDS[1:]},
}
ACADEMIC_RENAMES = {
    "dc.description.degree": "local.course.name",
    "dc.publisher.department": "local.campus.name",
}
SOURCE_FIELD = "local.identifier.legacy"
MANIFEST_NAME = "people.json"
PROFILE_FIELDS = {
    "email": "person.email",
    "lattes": "person.identifier.lattes",
    "degree": "local.person.degree",
}


def write_json(path: Path, data: dict) -> None:
    """Publica um manifesto completo; nunca deixa JSON parcialmente escrito."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False,
        ) as output:
            temporary = Path(output.name)
            json.dump(data, output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _name(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", str(value))).strip()


def normalize_email(value):
    value = _name(value)
    if re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,63}", value):
        local, domain = value.rsplit("@", 1)
        return f"{local}@{domain.lower()}"
    return None


def normalize_lattes(value):
    value = _name(value)
    if re.fullmatch(r"[0-9]{16}", value):
        return f"https://lattes.cnpq.br/{value}"
    if value.lower().startswith("lattes.cnpq.br/"):
        value = "https://" + value
    try:
        url = urlsplit(value)
        if (url.scheme in ("http", "https") and url.netloc.lower() == "lattes.cnpq.br"
                and re.fullmatch(r"/[0-9]{16}/?", url.path)):
            return f"https://lattes.cnpq.br/{url.path.strip('/')}"
    except ValueError:
        pass
    return None


def _profile(record, key, issues):
    profile = {}
    for field, normalize in (("email", normalize_email), ("lattes", normalize_lattes),
                             ("degree", lambda value: _name(value) or None)):
        if field not in record:
            continue
        raw = record[field]
        profile[field] = normalize(raw)
        if _name(raw) and not profile[field]:
            issue = {"person": key, "field": field, "reason": "invalid_format"}
            if issue not in issues:
                issues.append(issue)
    return profile


def _profile_metadata(person):
    return {field: [{"value": person[key]}] for key, field in PROFILE_FIELDS.items() if person.get(key)}


def build_manifest(rows: list[dict]) -> dict:
    """Preserva tabela+ID e papel; homônimos não são conciliados pelo nome."""
    manifest = {"version": 1, "people": {}, "items": {}}
    issues = []
    for row in rows:
        item_id = str(int(row["id_origem"]))
        if item_id in manifest["items"]:
            raise ValueError(f"Publicação duplicada: {item_id}")
        raw = row.get("pessoas")
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict) or set(raw) != set(PERSON_FIELDS):
            raise ValueError(f"item_{item_id}: consulta deve fornecer pessoas por ID e papel")
        participations = {}
        for field in PERSON_FIELDS:
            records = raw[field]
            if not isinstance(records, list):
                raise ValueError(f"item_{item_id}: lista de pessoas inválida em {field}")
            keys = []
            for record in records:
                source_id = record["id"]
                if isinstance(source_id, bool) or not str(source_id).isdigit() or int(source_id) <= 0:
                    raise ValueError(f"item_{item_id}: ID de pessoa inválido")
                if record.get("source") != SOURCE_TABLES[field]:
                    raise ValueError(f"item_{item_id}: tabela de origem incompatível com {field}")
                key = f"odoo:{record['source']}:{int(source_id)}"
                given = _name(record.get("given_name"))
                family = _name(record.get("family_name"))
                label = ", ".join(part for part in (family, given) if part)
                if not label or "||" in label:
                    raise ValueError(f"{key}: nome vazio ou contém separador reservado")
                person = {"given_name": given, "family_name": family, "name": label,
                          **_profile(record, key, issues)}
                previous = manifest["people"].get(key)
                if previous is not None and previous != person:
                    raise ValueError(f"Cadastro conflitante para {key}")
                manifest["people"][key] = person
                if key in keys:
                    raise ValueError(f"item_{item_id}: participação duplicada de {key} em {field}")
                keys.append(key)
            participations[field] = keys
            # A mesma lista gera o texto SAF e o vínculo; não associa por posição
            # entre duas agregações SQL independentes.
            row[field] = "||".join(manifest["people"][key]["name"] for key in keys) or None
        manifest["items"][item_id] = participations
    if issues:
        # Não replica endereços ou URLs inválidos em mensagens/relatórios.
        manifest["profile_issues"] = issues
    return manifest


def read_manifest(saf_dir: Path) -> dict:
    data = json.loads((saf_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("people"), dict) or not isinstance(data.get("items"), dict):
        raise ValueError("Manifesto de pessoas inválido ou versão não suportada")
    # Valida também manifestos retomados/editados antes de qualquer escrita REST.
    referenced = set()
    for item_id, fields in data["items"].items():
        if not str(item_id).isdigit() or int(item_id) <= 0 or set(fields) != set(PERSON_FIELDS):
            raise ValueError("Publicação ou papéis inválidos no manifesto")
        for field, keys in fields.items():
            if not isinstance(keys, list) or len(keys) != len(set(keys)):
                raise ValueError("Participações inválidas ou duplicadas")
            for key in keys:
                referenced.add(key)
                person = data["people"][key]
                prefix = f"odoo:{SOURCE_TABLES[field]}:"
                if not key.startswith(prefix) or not key[len(prefix):].isdigit():
                    raise ValueError(f"Identificador de origem inválido: {key}")
                if not person.get("name") or person["name"] != ", ".join(
                    part for part in (person.get("family_name"), person.get("given_name")) if part
                ):
                    raise ValueError(f"Nome inconsistente: {key}")
                issues = []
                if _profile(person, key, issues) != {k: person[k] for k in PROFILE_FIELDS if k in person} or issues:
                    raise ValueError(f"Perfil não normalizado: {key}")
    if referenced != set(data["people"]):
        raise ValueError("Manifesto contém pessoas sem participação no lote")
    return data


def _refresh_profiles(saf_dir):
    """Reextrai apenas o manifesto do lote, em transação de origem somente de leitura."""
    previous = read_manifest(saf_dir)
    sql = (Path(__file__).resolve().parents[2] / "sql/extract_metadata.sql").read_text().rstrip().rstrip(";")
    with psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5440"),
        dbname=os.getenv("DB_NAME", "biblioteca"), user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        options="-c default_transaction_read_only=on",
    ) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(f'SELECT source.* FROM ({sql}) AS source WHERE source."id_origem" = ANY(%s)',
                           (list(map(int, previous["items"])),))
            updated = build_manifest(cursor.fetchall())
    if updated["items"] != previous["items"] or set(updated["people"]) != set(previous["people"]):
        raise ValueError("Participações mudaram na origem; revise o lote antes de atualizar perfis")
    for key, person in previous["people"].items():
        if any(person[field] != updated["people"][key][field] for field in ("name", "given_name", "family_name")):
            raise ValueError(f"Nome mudou na origem: {key}; revisão necessária")
    return updated


def _json(response, expected=(200,)) -> dict:
    if response is None or response.status_code not in expected:
        status = getattr(response, "status_code", "sem resposta")
        raise RuntimeError(f"API DSpace retornou {status}; operação interrompida")
    return response.json()


def _values(metadata, field):
    return [value["value"] for value in metadata.get(field, [])]


def _canonical(values):
    return [
        {
            **{key: value.get(key, default) for key, default in (
                ("value", None), ("language", None), ("authority", None), ("confidence", -1),
            )},
            **({"securityLevel": value["securityLevel"]} if "securityLevel" in value else {}),
        }
        for value in values
    ]


def _validate_fields(metadata, fields, people, person_ids=None):
    for old, new in ACADEMIC_RENAMES.items():
        # Uma cópia interrompida pode ter publicado apenas o prefixo do campo.
        if old in metadata and new in metadata and _canonical(metadata[new]) != _canonical(metadata[old])[:len(metadata[new])]:
            raise ValueError(f"Valores conflitantes em {old} e {new}")
    for field, keys in fields.items():
        current = metadata.get(field, [])
        if Counter(value["value"] for value in current) != Counter(people[key]["name"] for key in keys):
            raise ValueError(f"Valores de {field} divergem da extração; revise o item antes de vincular")
        # A ordem do item é preservada. Homônimos com autoridades diferentes
        # podem ser distinguidos, mas texto puro ambíguo exige revisão.
        names = [people[key]["name"] for key in keys]
        if len(names) != len(set(names)):
            if person_ids is None or any(not value.get("authority") for value in current):
                raise ValueError(f"Homônimos ambíguos em {field}; conciliação necessária")
        if person_ids is not None:
            by_name = {}
            for key in keys:
                by_name.setdefault(people[key]["name"], set()).add(person_ids.get(key))
            used = set()
            for value in current:
                authority = value.get("authority")
                if authority:
                    if authority not in by_name[value["value"]] or authority in used:
                        raise ValueError(f"Autoridade conflitante em {field}")
                    used.add(authority)


@dataclass
class PeopleApplicationResult:
    created: int = 0
    reused: int = 0
    items_updated: int = 0
    items_unchanged: int = 0
    people_updated: int = 0
    profile_issues: int = 0


def apply_people(saf_bundle_dir=None, collection_uuid=None, *, dry_run=False, refresh_profiles=False):
    """Serializa as escritas de um SAF; simulação não escreve nem o lock."""
    load_dotenv()
    saf_dir = Path(saf_bundle_dir or os.getenv("SAF_BUNDLE_DIR", "saf_bundle"))
    if dry_run:
        return _apply_people(saf_dir, collection_uuid, dry_run=True, refresh_profiles=refresh_profiles)
    # O diretório deve existir: a extração precede a aplicação.
    with (saf_dir / "people.lock").open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Outra migração de pessoas está usando este SAF") from exc
        return _apply_people(saf_dir, collection_uuid, refresh_profiles=refresh_profiles)


def _apply_people(saf_bundle_dir=None, collection_uuid=None, *, dry_run=False, refresh_profiles=False):
    """Cria/reutiliza Person e vincula os trabalhos importados por autoridade.

    Exige backend preparado para Authority Framework. Não altera o modelo do
    servidor, não cria EPersons e não substitui todos os metadados de um item.
    """
    load_dotenv()
    saf_dir = Path(saf_bundle_dir or os.getenv("SAF_BUNDLE_DIR", "saf_bundle"))
    data = _refresh_profiles(saf_dir) if refresh_profiles else read_manifest(saf_dir)
    result = PeopleApplicationResult()
    result.profile_issues = len(data.get("profile_issues", []))
    if not data["items"]:
        return result
    collection_uuid = str(UUID(collection_uuid or os.getenv("DSPACE_PERSON_COLLECTION_UUID", "")))
    api_url = os.getenv("DSPACE_API_URL", "http://localhost:8080/server/api").rstrip("/")
    client = DSpaceClient(
        api_endpoint=api_url,
        username=os.getenv("DSPACE_API_USER", "test@test.edu"),
        password=os.getenv("DSPACE_API_PASSWORD", "admin"),
    )
    if not client.authenticate():
        raise RuntimeError("Falha na autenticação com a API REST do DSpace")
    mode = _json(client.api_get(f"{api_url}/config/properties/relationship.enable-virtual-metadata"))
    if mode.get("values") != ["false"]:
        raise RuntimeError("Pessoas exigem Authority Framework e a propriedade REST relationship.enable-virtual-metadata=false")
    collection = _json(client.api_get(
        f"{api_url}/core/collections/{collection_uuid}", params={"projection": "allLanguages"},
    ))
    if _values(collection["metadata"], "dspace.entity.type") != ["Person"]:
        raise ValueError("A coleção de pessoas deve ter tipo Person")

    # Usa a listagem administrativa baseada no banco; não depende de o Solr
    # já ter indexado a criação anterior para recuperar uma execução interrompida.
    person_ids = {}
    person_items = {}
    page = 0
    while True:
        response = _json(client.api_get(f"{api_url}/core/items", params={
            "page": page, "size": 100, "projection": "allLanguages",
        }))
        for item in response.get("_embedded", {}).get("items", []):
            metadata = item["metadata"]
            for key in _values(metadata, SOURCE_FIELD):
                if key not in data["people"]:
                    continue
                if _values(metadata, "dspace.entity.type") != ["Person"]:
                    raise ValueError(f"Identificador {key} associado a item sem tipo Person")
                if key in person_ids and person_ids[key] != item["uuid"]:
                    raise ValueError(f"Mais de uma Person para {key}")
                person_ids[key] = str(UUID(item["uuid"]))
                person_items[item["uuid"]] = item
        if page + 1 >= response.get("page", {}).get("totalPages", 1):
            break
        page += 1

    checkpoint_path = saf_dir / "people-map.json"
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("api_url") != api_url or checkpoint.get("collection_uuid") != collection_uuid:
            raise ValueError("Mapa de pessoas pertence a outro destino; use um SAF separado")
        for key, person_uuid in checkpoint.get("people", {}).items():
            if key in data["people"] and person_ids.get(key) != person_uuid:
                raise ValueError(f"Person {key} ausente ou divergente do mapa; revisão necessária")

    handles = read_mapfiles(str(saf_dir))
    missing = set(map(int, data["items"])) - set(handles)
    if missing:
        raise ValueError(f"Publicações sem handle: {sorted(missing)[:10]}; conclua/revise a importação SAF")
    # Pré-valida todos os trabalhos antes de criar pessoas ou alterar valores.
    items = {}
    for source_id, fields in data["items"].items():
        resolved = client.resolve_identifier_to_dso(handles[int(source_id)])
        if resolved is None:
            raise ValueError(f"Handle não resolvido para item_{source_id}")
        item_uuid = str(UUID(resolved.uuid))
        item = _json(client.api_get(f"{api_url}/core/items/{item_uuid}", params={"projection": "allLanguages"}))
        _validate_fields(item["metadata"], fields, data["people"], person_ids)
        items[source_id] = item

    # Valida todos os perfis existentes antes de qualquer escrita. Uma fusão
    # manual de identidades também não pode escolher entre perfis conflitantes.
    profile_targets = {}
    for key, person in data["people"].items():
        uid = person_ids.get(key)
        for field, values in _profile_metadata(person).items():
            desired = values[0]["value"]
            target = (uid or key, field)
            if target in profile_targets and profile_targets[target] != desired:
                raise ValueError(f"Perfis conflitantes para {key} em {field}")
            profile_targets[target] = desired
            current = _values(person_items[uid]["metadata"], field) if uid else []
            if current and desired not in current:
                raise ValueError(f"Perfil existente diverge de {key} em {field}; revisão necessária")

    def save_field(item, field, desired):
        # DSpace 10.1 insere com add e extrai só o primeiro elemento de arrays.
        # Atualiza cada ocorrência com um objeto, preservando ordem e segurança.
        current = _canonical(item["metadata"].get(field, []))
        for index, value in enumerate(_canonical(desired)):
            if index < len(current) and current[index] == value:
                continue
            operation = "replace" if index < len(current) else "add"
            suffix = f"/{index}" if operation == "replace" else ("/-" if current else "")
            expected = deepcopy(current)
            if operation == "replace":
                expected[index] = value
            else:
                expected.append(value)
            if not dry_run:
                saved = _json(client.api_patch(
                    url=f"{api_url}/core/items/{item['uuid']}", operation=operation,
                    path=f"/metadata/{field}{suffix}", value=value,
                    params={"projection": "allLanguages"},
                ))
                if _canonical(saved["metadata"].get(field, [])) != expected:
                    raise RuntimeError(f"A API não confirmou a gravação de {field}")
            current = expected
        item["metadata"][field] = current

    def remove_field(item, field):
        if not dry_run:
            saved = _json(client.api_patch(
                url=f"{api_url}/core/items/{item['uuid']}", operation="remove",
                path=f"/metadata/{field}", value=None,
                params={"projection": "allLanguages"},
            ))
            if field in saved["metadata"]:
                raise RuntimeError(f"A API não confirmou a remoção de {field}")
        item["metadata"].pop(field, None)

    if refresh_profiles and not dry_run:
        write_json(saf_dir / MANIFEST_NAME, data)
    enriched = set()
    for key, person in data["people"].items():
        profile = _profile_metadata(person)
        if key in person_ids:
            result.reused += 1
            item = person_items[person_ids[key]]
            for field, values in profile.items():
                if not item["metadata"].get(field):
                    save_field(item, field, values)
                    enriched.add(item["uuid"])
            continue
        result.created += 1
        if dry_run:
            person_ids[key] = f"dry-run:{key}"
            continue
        metadata = {
            "dc.title": [{"value": person["name"]}],
            "dspace.entity.type": [{"value": "Person"}],
            SOURCE_FIELD: [{"value": key}], **profile,
        }
        for field, name in (("person.givenName", "given_name"), ("person.familyName", "family_name")):
            if person[name]:
                metadata[field] = [{"value": person[name]}]
        created = _json(client.api_post(f"{api_url}/core/items", params={"owningCollection": collection_uuid}, json={
            "name": person["name"], "metadata": metadata,
            "inArchive": True, "discoverable": True, "withdrawn": False, "type": "item",
        }), expected=(201,))
        person_ids[key] = str(UUID(created["uuid"]))
        write_json(checkpoint_path, {"api_url": api_url, "collection_uuid": collection_uuid, "people": person_ids})
    result.people_updated = len(enriched)

    for source_id, item in items.items():
        metadata = item["metadata"]
        fields = data["items"][source_id]
        _validate_fields(metadata, fields, data["people"], person_ids)
        changed = False
        for old, new in ACADEMIC_RENAMES.items():
            if old not in metadata:
                continue
            save_field(item, new, metadata[old])
            # A cópia é confirmada antes de remover o campo antigo. Uma
            # interrupção entre as operações pode ser retomada sem perda.
            remove_field(item, old)
            changed = True
        for field, keys in fields.items():
            current = metadata.get(field, [])
            desired = deepcopy(current)
            by_name = {data["people"][key]["name"]: person_ids[key] for key in keys}
            for value in desired:
                value["authority"] = value.get("authority") or by_name[value["value"]]
                value["confidence"] = 600  # Choices.CF_ACCEPTED
            if _canonical(current) != _canonical(desired):
                save_field(item, field, desired)
                changed = True
        if changed:
            result.items_updated += 1
        else:
            result.items_unchanged += 1
    if not dry_run:
        write_json(checkpoint_path, {"api_url": api_url, "collection_uuid": collection_uuid, "people": person_ids})
    return result
