import os
import re
import uuid
from collections.abc import Iterator
import requests
import psycopg2
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Banco de origem (legado)
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5440")
DB_NAME     = os.getenv("DB_NAME", "biblioteca")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# ── Banco do DSpace
DSPACE_DB_HOST     = os.getenv("DSPACE_DB_HOST", "localhost")
DSPACE_DB_PORT     = os.getenv("DSPACE_DB_PORT", "5432")
DSPACE_DB_NAME     = os.getenv("DSPACE_DB_NAME", "dspace")
DSPACE_DB_USER     = os.getenv("DSPACE_DB_USER", "dspace")
DSPACE_DB_PASSWORD = os.getenv("DSPACE_DB_PASSWORD", "dspace")

# ── Solr
SOLR_URL        = os.getenv("SOLR_URL", "http://localhost:8983/solr")
SOLR_BATCH_SIZE = int(os.getenv("SOLR_BATCH_SIZE", "500"))

# ── SAF
SAF_BUNDLE_DIR = os.getenv("SAF_BUNDLE_DIR", "saf_bundle")

# Padrão do mapfile: "item_<id_origem>   <handle>"
MAPFILE_LINE_RE = re.compile(r"^item_(\d+)\s+(\S+)\s*$")


def _connect_origem():
    """Conexão com o banco de origem (legado)."""
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )


def _connect_dspace():
    """Conexão com o banco PostgreSQL do DSpace."""
    return psycopg2.connect(
        host=DSPACE_DB_HOST, port=DSPACE_DB_PORT, dbname=DSPACE_DB_NAME,
        user=DSPACE_DB_USER, password=DSPACE_DB_PASSWORD,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Leitura dos mapfiles → {id_origem: handle}
# ─────────────────────────────────────────────────────────────────────────────

def read_mapfiles(saf_bundle_dir: str) -> dict:
    """
    Percorre todos os mapfile.txt dentro do SAF bundle e retorna o mapeamento
    {id_origem (int) → handle (str)}.

    Formato esperado de cada linha do mapfile:
        item_123    123456789/42
    """
    bundle = Path(saf_bundle_dir)
    mapping = {}

    mapfiles = sorted(bundle.rglob("mapfile.txt"))
    if not mapfiles:
        raise FileNotFoundError(
            f"Nenhum mapfile.txt encontrado em '{bundle}'. "
            "Execute a importação SAF antes de injetar estatísticas."
        )

    print(f"Encontrados {len(mapfiles)} mapfile(s). Lendo...")
    for mf in mapfiles:
        for line_number, line in enumerate(
            mf.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.strip()
            if not stripped:
                continue
            match = MAPFILE_LINE_RE.fullmatch(stripped)
            if match is None:
                raise ValueError(
                    f"Linha inválida em {mf}:{line_number}: {line!r}"
                )
            id_origem = int(match.group(1))
            handle = match.group(2)
            previous = mapping.get(id_origem)
            if previous is not None and previous != handle:
                raise ValueError(
                    f"item_{id_origem} possui handles conflitantes: "
                    f"{previous} e {handle}"
                )
            mapping[id_origem] = handle

    print(f"  → {len(mapping)} itens mapeados (id_origem → handle)")
    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# 2. Resolução de handle → UUID do item no banco do DSpace
# ─────────────────────────────────────────────────────────────────────────────

def resolve_uuids_from_dspace(handles: list) -> dict:
    """
    Consulta o banco PostgreSQL do DSpace e retorna {handle → uuid} para os
    handles fornecidos.
    """
    if not handles:
        return {}

    print(f"Resolvendo {len(handles)} handles no banco do DSpace...")
    conn = _connect_dspace()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT h.handle, i.uuid::text
                FROM handle h
                JOIN item i ON i.uuid = h.resource_id
                WHERE h.handle = ANY(%s)
                """,
                (handles,),
            )
            result = {row[0]: row[1] for row in cur.fetchall()}
    finally:
        conn.close()

    unresolved = set(handles) - set(result)
    if unresolved:
        sample = list(unresolved)[:5]
        print(f"  ⚠️  {len(unresolved)} handle(s) não resolvidos (primeiros 5): {sample}")
    print(f"  → {len(result)} UUIDs resolvidos")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3. Busca de contagens e datas do banco de origem
# ─────────────────────────────────────────────────────────────────────────────

def fetch_view_counts() -> dict:
    """
    Retorna {id_origem → {'visualizacoes': N, 'ano_pub': YYYY}} do banco de origem.
    Inclui apenas registros com visualizacoes > 0.
    """
    print("Buscando contagens de visualizações no banco de origem...")
    conn = _connect_origem()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, visualizacoes, ano_pub
                FROM ud_biblioteca_publicacao
                WHERE visualizacoes IS NOT NULL AND visualizacoes > 0
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    data = {
        row[0]: {
            "visualizacoes": int(row[1]),
            "ano_pub": int(row[2]) if row[2] else None,
        }
        for row in rows
    }
    total_views = sum(v["visualizacoes"] for v in data.values())
    print(f"  → {len(data)} itens com visualizações. Total de eventos: {total_views:,}")
    return data


# ─────────────────────────────────────────────────────────────────────────────
# 4. Geração de documentos Solr
# ─────────────────────────────────────────────────────────────────────────────

def _uniform_timestamps(n: int, start: datetime, end: datetime) -> list:
    """
    Gera N timestamps distribuídos uniformemente entre start e end.
    Retorna strings no formato ISO 8601 com sufixo 'Z' (Solr TrieDateField).
    """
    if n < 0:
        raise ValueError("A quantidade de visualizações não pode ser negativa")
    if n == 0:
        return []
    if n == 1:
        mid = start + (end - start) / 2
        return [mid.strftime("%Y-%m-%dT%H:%M:%SZ")]

    span = (end - start).total_seconds()
    step = span / (n - 1) if n > 1 else 0
    return [
        (start + timedelta(seconds=i * step)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for i in range(n)
    ]


def iter_solr_docs(
    item_uuid: str,
    n_views: int,
    ano_pub,
    *,
    now: datetime | None = None,
) -> Iterator[dict]:
    """
    Gera n_views documentos Solr sintéticos para um item (type=2, view).
    Os timestamps são distribuídos uniformemente entre jan/ano_pub e hoje.
    """
    if n_views < 0:
        raise ValueError("A quantidade de visualizações não pode ser negativa")
    now = now or datetime.now(tz=timezone.utc)
    if now.tzinfo is None:
        raise ValueError("'now' precisa conter fuso horário")

    try:
        publication_year = int(ano_pub) if ano_pub else None
    except (TypeError, ValueError):
        publication_year = None

    if publication_year and 1000 <= publication_year <= 9999:
        start = datetime(publication_year, 1, 1, tzinfo=timezone.utc)
    else:
        # Fallback: distribui nos últimos 5 anos
        start = now - timedelta(days=5 * 365)

    # Garante que start < now
    if start >= now:
        start = now - timedelta(days=365)

    if n_views == 1:
        timestamps = [start + (now - start) / 2]
    elif n_views > 1:
        step = (now - start) / (n_views - 1)
        timestamps = (start + index * step for index in range(n_views))
    else:
        timestamps = ()

    for index, timestamp in enumerate(timestamps):
        yield {
            # UUID determinístico: uma reexecução sobrescreve os mesmos
            # eventos no Solr em vez de duplicar a contagem histórica.
            "uid":             str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"dspace-migration:view:{item_uuid}:{index}",
            )),
            "type":            2,                      # 2 = item view no DSpace
            "id":              item_uuid,
            "owningItem":      item_uuid,
            "time":            timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ip":              "127.0.0.1",
            "isBot":           False,
            "statistics_type": "view",
        }


def generate_solr_docs(
    item_uuid: str,
    n_views: int,
    ano_pub,
    *,
    now: datetime | None = None,
) -> list:
    """Versão materializada de :func:`iter_solr_docs`, útil para inspeção."""
    return list(iter_solr_docs(item_uuid, n_views, ano_pub, now=now))


# ─────────────────────────────────────────────────────────────────────────────
# 5. Envio ao Solr em lotes
# ─────────────────────────────────────────────────────────────────────────────

def _post_to_solr(docs: list, solr_url: str) -> None:
    """Envia um lote de documentos ao Solr statistics via HTTP."""
    url = f"{solr_url}/statistics/update/json?commit=false"
    resp = requests.post(url, json=docs, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Erro ao enviar para Solr [{resp.status_code}]: {resp.text[:300]}"
        )


def _commit_solr(solr_url: str) -> None:
    """Faz commit final no Solr."""
    url = f"{solr_url}/statistics/update?commit=true"
    resp = requests.get(url, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Erro ao fazer commit no Solr [{resp.status_code}]: {resp.text[:200]}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Orquestração principal
# ─────────────────────────────────────────────────────────────────────────────

def inject_statistics(
    saf_bundle_dir=None,
    solr_url=None,
    dry_run: bool = False,
) -> None:
    """
    Pipeline completo de injeção de estatísticas de visualizações no DSpace.

    1. Lê mapfiles → {id_origem: handle}
    2. Resolve handles → UUIDs no banco do DSpace
    3. Busca contagens de visualizações no banco de origem
    4. Gera documentos Solr e envia em lotes
    """
    saf_dir = saf_bundle_dir or SAF_BUNDLE_DIR
    solr    = solr_url or SOLR_URL
    if SOLR_BATCH_SIZE <= 0:
        raise ValueError("SOLR_BATCH_SIZE deve ser maior que zero")

    # ── Etapa 1: mapfiles
    id_to_handle = read_mapfiles(saf_dir)

    # ── Etapa 2: resolver UUIDs
    all_handles    = list(id_to_handle.values())
    handle_to_uuid = resolve_uuids_from_dspace(all_handles)

    # ── Montar id_origem → uuid
    id_to_uuid = {}
    for id_origem, handle in id_to_handle.items():
        item_uuid = handle_to_uuid.get(handle)
        if item_uuid:
            id_to_uuid[id_origem] = item_uuid

    # ── Etapa 3: contagens
    view_counts = fetch_view_counts()

    # ── Cruzamento
    items_to_inject = {
        id_origem: {**view_counts[id_origem], "uuid": id_to_uuid[id_origem]}
        for id_origem in view_counts
        if id_origem in id_to_uuid
    }

    skipped = len(view_counts) - len(items_to_inject)
    if skipped:
        print(f"  ⚠️  {skipped} itens com views não encontrados no DSpace (sem UUID). Pulados.")

    total_docs = sum(v["visualizacoes"] for v in items_to_inject.values())
    print(f"\nPronto para injetar {total_docs:,} documentos Solr para {len(items_to_inject)} itens.")

    if dry_run:
        print("  [DRY-RUN] Nenhum dado foi enviado ao Solr.")
        return

    # ── Etapa 4: gerar e enviar em lotes
    batch      = []
    items_done = 0
    docs_done  = 0

    for id_origem, info in items_to_inject.items():
        docs = iter_solr_docs(
            item_uuid=info["uuid"],
            n_views=info["visualizacoes"],
            ano_pub=info["ano_pub"],
        )
        for doc in docs:
            batch.append(doc)
            if len(batch) == SOLR_BATCH_SIZE:
                _post_to_solr(batch, solr)
                docs_done += len(batch)
                batch = []

        items_done += 1
        if items_done % 200 == 0:
            print(f"  Processados {items_done}/{len(items_to_inject)} itens ({docs_done:,} docs enviados)...")

    # Envia o restante
    if batch:
        _post_to_solr(batch, solr)
        docs_done += len(batch)

    # Commit final
    print(f"\nFazendo commit no Solr ({docs_done:,} documentos)...")
    _commit_solr(solr)
    print("✔ Injeção de estatísticas concluída com sucesso.")
    print(f"  Total de documentos injetados: {docs_done:,}")
    print(f"  Itens com estatísticas migradas: {items_done}")
