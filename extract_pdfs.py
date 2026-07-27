import base64
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
BATCH_SIZE     = int(os.getenv("BATCH_SIZE", "50"))

# ---------------------------------------------------------------------------
# Filter — change to "false" to extract items where exibir_pdf IS false.
# ---------------------------------------------------------------------------
EXIBIR_PDF_FILTER = True  # change to False to extract restricted files

# 1. Consulta apenas os IDs válidos (ignora registros com publicacao_id nulo)
IDS_QUERY = """
    SELECT publicacao_id
    FROM ud_biblioteca_anexo
    WHERE publicacao_id IS NOT NULL
      AND exibir_pdf = %(exibir_pdf)s
    ORDER BY publicacao_id;
"""

# 2. Consulta de binários por lote específico de IDs
BATCH_BINARY_QUERY = """
    SELECT publicacao_id, arquivo
    FROM ud_biblioteca_anexo
    WHERE publicacao_id = ANY(%(id_list)s)
    ORDER BY publicacao_id;
"""


def decode_pdf_bytes(raw_data) -> bytes:
    """Decodifica os dados do PDF garantindo arquivo binário válido (%PDF-).
    Trata memoryview, hex format de bytea do PostgreSQL (\\x...) e Base64 do Odoo.
    """
    if raw_data is None:
        return b""

    # Converte memoryview / bytearray / str para bytes
    if isinstance(raw_data, memoryview):
        data = bytes(raw_data)
    elif isinstance(raw_data, str):
        data = raw_data.encode("utf-8")
    else:
        data = bytes(raw_data)

    # 1. Se já for o binário puro do PDF (magic bytes %PDF-)
    if data.startswith(b"%PDF-"):
        return data

    # 2. Se for formato Hex do PostgreSQL (\x25504446...)
    if data.startswith(b"\\x"):
        try:
            hex_str = data[2:].decode("ascii")
            decoded = bytes.fromhex(hex_str)
            return decoded
        except Exception:
            pass

    # 3. Se for string Base64 (típico do Odoo, onde %PDF- vira JVBERi...)
    if data.startswith(b"JVBERi"):
        try:
            return base64.b64decode(data)
        except Exception:
            pass

    # 4. Tenta decodificação Base64 genérica
    try:
        decoded = base64.b64decode(data)
        if decoded.startswith(b"%PDF-"):
            return decoded
    except Exception:
        pass

    # 5. Tenta decodificação Hex genérica
    try:
        decoded = bytes.fromhex(data.decode("ascii"))
        if decoded.startswith(b"%PDF-"):
            return decoded
    except Exception:
        pass

    return data


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
        # 1. Busca apenas a lista de IDs inteiros válidos
        with conn.cursor() as cur:
            logger.info("Buscando lista de IDs a processar...")
            cur.execute(IDS_QUERY, {"exibir_pdf": EXIBIR_PDF_FILTER})
            all_ids = [row[0] for row in cur.fetchall()]

        total_records = len(all_ids)
        logger.info(
            "Total de IDs obtidos (exibir_pdf = %s): %d",
            EXIBIR_PDF_FILTER,
            total_records,
        )
        logger.info("Tamanho do lote por query: %d IDs", BATCH_SIZE)

        if total_records == 0:
            logger.info("Nenhum registro encontrado.")
            return

        # Dividir a lista de IDs em pequenos pedaços (chunks)
        id_chunks = [
            all_ids[i : i + BATCH_SIZE]
            for i in range(0, total_records, BATCH_SIZE)
        ]

        written       = 0
        skipped_null  = 0
        skipped_nodir = 0
        processed_total = 0

        # 2. Iterar lote a lote fazendo queries individuais pelos binários
        with conn.cursor() as cur:
            for batch_index, chunk in enumerate(id_chunks, start=1):
                logger.info(
                    "Processando lote %d/%d (IDs %s a %s)... [%d/%d]",
                    batch_index,
                    len(id_chunks),
                    chunk[0],
                    chunk[-1],
                    min(processed_total + len(chunk), total_records),
                    total_records,
                )

                # Busca apenas os binários dos IDs deste lote específico
                cur.execute(BATCH_BINARY_QUERY, {"id_list": chunk})
                rows = cur.fetchall()

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

                    # C. Decodificação do binário (Base64, Hex ou Raw) e gravação
                    dest = item_dir / "documento.pdf"
                    try:
                        pdf_bytes = decode_pdf_bytes(arquivo)
                        if not pdf_bytes:
                            logger.warning(
                                "Falha ao decodificar PDF para publicacao_id=%s — registro ignorado.",
                                publicacao_id,
                            )
                            skipped_null += 1
                            continue

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

                # Liberar explicitamente referências a rows do lote anterior
                del rows

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
