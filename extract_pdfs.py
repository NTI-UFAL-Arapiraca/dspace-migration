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
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "biblioteca")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

SAF_BUNDLE_DIR = Path(os.getenv("SAF_BUNDLE_DIR", "saf_bundle"))

# ---------------------------------------------------------------------------
# Filter — change to "false" to extract items where exibir_pdf IS false.
# ---------------------------------------------------------------------------
EXIBIR_PDF_FILTER = True  # change to False to extract restricted files

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
        with conn.cursor() as cur:
            logger.info(
                "Executando consulta (exibir_pdf = %s)...", EXIBIR_PDF_FILTER
            )
            cur.execute(QUERY, {"exibir_pdf": EXIBIR_PDF_FILTER})
            rows = cur.fetchall()
            logger.info("Total de registros retornados: %d", len(rows))

            # Counters
            written       = 0
            skipped_null  = 0
            skipped_nodir = 0

            for publicacao_id, arquivo in rows:
                item_dir = SAF_BUNDLE_DIR / f"item_{publicacao_id}"

                # 1. Check that the corresponding SAF folder exists
                if not item_dir.is_dir():
                    logger.warning(
                        "Pasta não encontrada para publicacao_id=%s → %s",
                        publicacao_id,
                        item_dir,
                    )
                    skipped_nodir += 1
                    continue

                # 2. Guard against null / empty binaries
                if not arquivo:
                    logger.warning(
                        "Arquivo binário nulo ou vazio para publicacao_id=%s — registro ignorado.",
                        publicacao_id,
                    )
                    skipped_null += 1
                    continue

                # 3. Write the binary PDF to the SAF folder
                dest = item_dir / "documento.pdf"
                try:
                    # psycopg2 returns bytea columns as memoryview
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

        # Final summary
        logger.info("=" * 60)
        logger.info("Extração concluída.")
        logger.info("  ✔ PDFs gravados com sucesso : %d", written)
        logger.info("  ✘ Pastas inexistentes       : %d", skipped_nodir)
        logger.info("  ⚠ Binários nulos/corrompidos: %d", skipped_null)
        logger.info("=" * 60)

    finally:
        conn.close()
        logger.info("Conexão com o banco encerrada.")


if __name__ == "__main__":
    extract_pdfs()
