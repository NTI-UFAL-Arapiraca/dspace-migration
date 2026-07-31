import base64
import logging
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

load_dotenv()

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5440")
DB_NAME     = os.getenv("DB_NAME", "biblioteca")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

SAF_BUNDLE_DIR = Path(os.getenv("SAF_BUNDLE_DIR", "saf_bundle"))
BATCH_SIZE     = int(os.getenv("BATCH_SIZE", "50"))
EXIBIR_PDF_FILTER = True

IDS_QUERY = """
    SELECT DISTINCT publicacao_id
    FROM ud_biblioteca_anexo
    WHERE publicacao_id IS NOT NULL
      AND exibir_pdf = %(exibir_pdf)s
    ORDER BY publicacao_id;
"""

BATCH_BINARY_QUERY = """
    SELECT publicacao_id, id, name, arquivo
    FROM ud_biblioteca_anexo
    WHERE publicacao_id = ANY(%(id_list)s)
      AND exibir_pdf = %(exibir_pdf)s
    ORDER BY publicacao_id, id;
"""

INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def sanitize_filename(name: str) -> str:
    """Remove ou substitui caracteres inválidos em nomes de arquivo."""
    cleaned = INVALID_FILENAME_CHARS.sub("_", name).strip()
    if len(cleaned) > 200:
        stem = Path(cleaned).stem[:195]
        suffix = Path(cleaned).suffix
        cleaned = stem + suffix
    return cleaned or "documento.pdf"


def decode_pdf_bytes(raw_data) -> bytes:
    """Decodifica os dados do PDF garantindo arquivo binário válido (%PDF-)."""
    if raw_data is None:
        return b""

    if isinstance(raw_data, memoryview):
        data = bytes(raw_data)
    elif isinstance(raw_data, str):
        data = raw_data.encode("utf-8")
    else:
        data = bytes(raw_data)

    if data.startswith(b"%PDF-"):
        return data

    if data.startswith(b"\\x"):
        try:
            return bytes.fromhex(data[2:].decode("ascii"))
        except Exception:
            pass

    if data.startswith(b"JVBERi"):
        try:
            return base64.b64decode(data)
        except Exception:
            pass

    try:
        decoded = base64.b64decode(data)
        if decoded.startswith(b"%PDF-"):
            return decoded
    except Exception:
        pass

    try:
        decoded = bytes.fromhex(data.decode("ascii"))
        if decoded.startswith(b"%PDF-"):
            return decoded
    except Exception:
        pass

    return data


def cleanup_orphaned_contents(saf_bundle_dir: Path) -> None:
    """Remove ou corrige arquivos 'contents' cujos arquivos listados não existem no disco."""
    if not saf_bundle_dir.is_dir():
        return

    cleaned = 0
    removed = 0
    for item_dir in saf_bundle_dir.glob("item_*"):
        contents_file = item_dir / "contents"
        if contents_file.is_file():
            lines = contents_file.read_text(encoding="utf-8").splitlines()
            valid_files = [
                line.strip()
                for line in lines
                if line.strip() and (item_dir / line.strip()).is_file()
            ]
            if valid_files:
                if len(valid_files) != len(lines):
                    contents_file.write_text("\n".join(valid_files) + "\n", encoding="utf-8")
                    cleaned += 1
            else:
                contents_file.unlink()
                removed += 1

    if cleaned > 0 or removed > 0:
        logger.info(
            "Limpeza de arquivos 'contents': %d corrigidos, %d removidos (itens sem anexos).",
            cleaned,
            removed,
        )


def connect() -> psycopg2.extensions.connection:
    """Establish and return a PostgreSQL connection."""
    logger.info(
        "Conectando ao banco %s em %s:%s...", DB_NAME, DB_HOST, DB_PORT
    )
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def extract_pdfs() -> None:
    conn = connect()
    logger.info("Conexão estabelecida com sucesso.")

    try:
        with conn.cursor() as cur:
            logger.info("Buscando lista de IDs únicos a processar...")
            cur.execute(IDS_QUERY, {"exibir_pdf": EXIBIR_PDF_FILTER})
            all_ids = [row[0] for row in cur.fetchall()]

        total_records = len(all_ids)
        logger.info(
            "Total de publicações únicas (exibir_pdf = %s): %d",
            EXIBIR_PDF_FILTER,
            total_records,
        )
        logger.info("Tamanho do lote por query: %d publicações", BATCH_SIZE)

        if total_records == 0:
            logger.info("Nenhum registro encontrado.")
            cleanup_orphaned_contents(SAF_BUNDLE_DIR)
            return

        id_chunks = [
            all_ids[i : i + BATCH_SIZE]
            for i in range(0, total_records, BATCH_SIZE)
        ]

        written         = 0
        skipped_null    = 0
        skipped_nodir   = 0
        processed_total = 0
        multi_attachment_pubs = 0

        with conn.cursor() as cur:
            for batch_index, chunk in enumerate(id_chunks, start=1):
                logger.info(
                    "Processando lote %d/%d (publicações %s a %s)... [%d/%d]",
                    batch_index,
                    len(id_chunks),
                    chunk[0],
                    chunk[-1],
                    processed_total + len(chunk),
                    total_records,
                )

                cur.execute(BATCH_BINARY_QUERY, {
                    "id_list": chunk,
                    "exibir_pdf": EXIBIR_PDF_FILTER,
                })
                rows = cur.fetchall()

                pub_attachments: dict = defaultdict(list)
                for publicacao_id, anexo_id, name, arquivo in rows:
                    pub_attachments[publicacao_id].append((anexo_id, name, arquivo))

                for publicacao_id in chunk:
                    item_dir = SAF_BUNDLE_DIR / f"item_{publicacao_id}"

                    if not item_dir.is_dir():
                        logger.warning(
                            "Pasta não encontrada para publicacao_id=%s → %s",
                            publicacao_id,
                            item_dir,
                        )
                        skipped_nodir += 1
                        continue

                    attachments = pub_attachments.get(publicacao_id, [])

                    if not attachments:
                        logger.warning(
                            "Nenhum anexo retornado para publicacao_id=%s — ignorado.",
                            publicacao_id,
                        )
                        skipped_null += 1
                        continue

                    if len(attachments) > 1:
                        multi_attachment_pubs += 1

                    used_names: set = set()
                    contents_lines: list = []

                    for anexo_id, raw_name, arquivo in attachments:
                        safe_name = sanitize_filename(raw_name or f"documento_{anexo_id}.pdf")
                        if safe_name in used_names:
                            stem = Path(safe_name).stem
                            suffix = Path(safe_name).suffix or ".pdf"
                            safe_name = f"{stem}_{anexo_id}{suffix}"
                        used_names.add(safe_name)

                        if not arquivo:
                            logger.warning(
                                "Arquivo binário nulo para publicacao_id=%s, anexo_id=%s (%s) — ignorado.",
                                publicacao_id,
                                anexo_id,
                                raw_name,
                            )
                            skipped_null += 1
                            continue

                        dest = item_dir / safe_name
                        try:
                            pdf_bytes = decode_pdf_bytes(arquivo)
                            if not pdf_bytes:
                                logger.warning(
                                    "Falha ao decodificar publicacao_id=%s, anexo_id=%s — ignorado.",
                                    publicacao_id,
                                    anexo_id,
                                )
                                skipped_null += 1
                                continue

                            dest.write_bytes(pdf_bytes)
                            contents_lines.append(safe_name)
                            written += 1
                            logger.debug(
                                "PDF gravado: %s (%d bytes)", dest, len(pdf_bytes)
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.warning(
                                "Falha ao gravar publicacao_id=%s, anexo=%s: %s — ignorado.",
                                publicacao_id,
                                safe_name,
                                exc,
                            )
                            skipped_null += 1

                    if contents_lines:
                        contents_path = item_dir / "contents"
                        contents_path.write_text("\n".join(contents_lines) + "\n", encoding="utf-8")

                processed_total += len(chunk)
                del rows

        cleanup_orphaned_contents(SAF_BUNDLE_DIR)

        logger.info("=" * 60)
        logger.info("Extração de PDFs concluída com sucesso!")
        logger.info("  ✔ Arquivos gravados com sucesso     : %d", written)
        logger.info("  📎 Publicações com múltiplos anexos : %d", multi_attachment_pubs)
        logger.info("  ✘ Pastas inexistentes               : %d", skipped_nodir)
        logger.info("  ⚠ Binários nulos/corrompidos        : %d", skipped_null)
        logger.info("=" * 60)

    finally:
        conn.close()
        logger.info("Conexão com o banco encerrada.")
