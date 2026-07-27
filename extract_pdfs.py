import logging
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5440")
DB_NAME     = os.getenv("DB_NAME", "biblioteca")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

SAF_BUNDLE_DIR = Path(os.getenv("SAF_BUNDLE_DIR", "saf_bundle"))
BATCH_SIZE     = int(os.getenv("BATCH_SIZE", "100"))

# ---------------------------------------------------------------------------
# Filter — change to "false" to extract items where exibir_pdf IS false.
# ---------------------------------------------------------------------------
EXIBIR_PDF_FILTER = True  # change to False to extract restricted files

COUNT_QUERY = """
    SELECT COUNT(*)
    FROM ud_biblioteca_anexo
    WHERE exibir_pdf = %(exibir_pdf)s;
"""

QUERY = """
    SELECT
        publicacao_id,
        arquivo
    FROM ud_biblioteca_anexo
    WHERE exibir_pdf = %(exibir_pdf)s
    ORDER BY publicacao_id;
"""


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
        # 1. Contagem total sem carregar os binários
        with conn.cursor() as count_cur:
            count_cur.execute(COUNT_QUERY, {"exibir_pdf": EXIBIR_PDF_FILTER})
            total_records = count_cur.fetchone()[0]

        logger.info(
            "Total de registros a processar (exibir_pdf = %s): %d",
            EXIBIR_PDF_FILTER,
            total_records,
        )
        logger.info("Tamanho do lote (batch_size): %d", BATCH_SIZE)

        # Counters
        written       = 0
        skipped_null  = 0
        skipped_nodir = 0
        processed_total = 0

        # 2. Utilização de cursor server-side nomeado para streaming em lotes
        # Evita carregar todos os binários (bytea) de uma só vez na RAM
        with conn.cursor(name="extract_pdf_server_cursor") as cur:
            cur.itersize = BATCH_SIZE
            cur.execute(QUERY, {"exibir_pdf": EXIBIR_PDF_FILTER})

            batch_num = 0
            while True:
                rows = cur.fetchmany(BATCH_SIZE)
                if not rows:
                    break

                batch_num += 1
                logger.info(
                    "Processando lote %d (%d registros)... [%d/%d]",
                    batch_num,
                    len(rows),
                    min(processed_total + len(rows), total_records),
                    total_records,
                )

                for publicacao_id, arquivo in rows:
                    processed_total += 1
                    item_dir = SAF_BUNDLE_DIR / f"item_{publicacao_id}"

                    # A. Verifica se a pasta SAF correspondente existe
                    if not item_dir.is_dir():
                        logger.warning(
                            "Pasta não encontrada para publicacao_id=%s → %s",
                            publicacao_id,
                            item_dir,
                        )
                        skipped_nodir += 1
                        continue

                    # B. Proteção contra binários nulos ou vazios
                    if not arquivo:
                        logger.warning(
                            "Arquivo binário nulo ou vazio para publicacao_id=%s — registro ignorado.",
                            publicacao_id,
                        )
                        skipped_null += 1
                        continue

                    # C. Gravação do arquivo PDF no diretório do item
                    dest = item_dir / "documento.pdf"
                    try:
                        pdf_bytes = bytes(arquivo)
                        dest.write_bytes(pdf_bytes)
                        written += 1
                        logger.debug(
                            "PDF gravado: %s (%d bytes)", dest, len(pdf_bytes)
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Falha ao gravar PDF para publicacao_id=%s: %s — registro ignorado.",
                            publicacao_id,
                            exc,
                        )
                        skipped_null += 1

        # Summary
        logger.info("=" * 60)
        logger.info("Extração concluída com sucesso!")
        logger.info("  ✔ PDFs gravados com sucesso : %d", written)
        logger.info("  ✘ Pastas inexistentes       : %d", skipped_nodir)
        logger.info("  ⚠ Binários nulos/corrompidos: %d", skipped_null)
        logger.info("=" * 60)

    finally:
        conn.close()
        logger.info("Conexão com o banco encerrada.")


if __name__ == "__main__":
    extract_pdfs()
