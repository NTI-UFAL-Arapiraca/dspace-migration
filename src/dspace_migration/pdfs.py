"""Extração e conversão de anexos binários do banco de dados PostgreSQL para SAF."""
from __future__ import annotations

import base64
import csv
import logging
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import psycopg2
from dotenv import load_dotenv
from dspace_migration.access import (
    build_contents_entry,
    contents_entry_filename,
    read_access_policies,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração via variáveis de ambiente
# ---------------------------------------------------------------------------

load_dotenv()

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5440")
DB_NAME     = os.getenv("DB_NAME", "biblioteca")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

SAF_BUNDLE_DIR    = Path(os.getenv("SAF_BUNDLE_DIR", "saf_bundle"))
BATCH_SIZE        = int(os.getenv("BATCH_SIZE", "50"))
GS_TIMEOUT        = int(os.getenv("GS_TIMEOUT", "300"))
EXIBIR_PDF_FILTER = True

# ---------------------------------------------------------------------------
# Queries SQL
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
PDF_MAGIC              = b"%PDF-"

GS_CMD_BASE = [
    "gs",
    "-dPDFA=2",
    "-dBATCH",
    "-dNOPAUSE",
    "-dNOOUTERSAVE",
    "-sProcessColorModel=DeviceRGB",
    "-sDEVICE=pdfwrite",
    "-sPDFACompatibilityPolicy=1",
]

ISSUES_CSV_FIELDS = [
    "publicacao_id",
    "anexo_id",
    "filename",
    "issue_type",
    "details",
    "action_taken",
]

# ---------------------------------------------------------------------------
# Tipos auxiliares
# ---------------------------------------------------------------------------


class Issue(NamedTuple):
    """Registro de anomalia/alerta ocorrido durante a extração."""
    publicacao_id: int | str
    anexo_id:      int | str
    filename:      str
    issue_type:    str
    details:       str
    action_taken:  str

    def as_dict(self) -> dict:
        return self._asdict()


@dataclass
class ExtractionStats:
    """Contadores consolidados da extração."""
    written:               int = 0
    non_pdf:               int = 0
    skipped_null:          int = 0
    skipped_nodir:         int = 0
    pdfa_failures:         int = 0
    multi_attachment_pubs: int = 0
    processed_total:       int = 0

# ---------------------------------------------------------------------------
# Utilitários de arquivo
# ---------------------------------------------------------------------------


def sanitize_filename(name: str) -> str:
    """Remove ou substitui caracteres inválidos em nomes de arquivo."""
    cleaned = INVALID_FILENAME_CHARS.sub("_", name).strip()
    if len(cleaned) > 200:
        cleaned = Path(cleaned).stem[:195] + Path(cleaned).suffix
    return cleaned or "documento.pdf"


def decode_file_bytes(raw_data) -> bytes:
    """Converte a representação armazenada no banco (bytea, base64, hex) para bytes puros.

    O PostgreSQL pode retornar dados binários em vários formatos dependendo da
    versão do driver e de como os dados foram inseridos originalmente.
    Tentamos os formatos mais comuns em ordem de custo crescente.
    """
    if raw_data is None:
        return b""

    if isinstance(raw_data, memoryview):
        data = bytes(raw_data)
    elif isinstance(raw_data, str):
        data = raw_data.encode("utf-8")
    else:
        data = bytes(raw_data)

    # Já é bytes puros (mais comum com psycopg2 em modo bytea)
    if data[:5] in (PDF_MAGIC, b"\x89PNG", b"GIF87", b"GIF89", b"\xff\xd8\xff"):
        return data

    # Hex escapado: b'\x25\x50\x44...'
    if data.startswith(b"\\x"):
        try:
            return bytes.fromhex(data[2:].decode("ascii"))
        except Exception:
            pass

    # Base64 literal (prefixo reconhecível de PDF codificado)
    if data.startswith(b"JVBERi"):
        try:
            return base64.b64decode(data)
        except Exception:
            pass

    # Base64 genérico
    try:
        decoded = base64.b64decode(data)
        if decoded[:5] == PDF_MAGIC:
            return decoded
    except Exception:
        pass

    # Hex ASCII puro
    try:
        decoded = bytes.fromhex(data.decode("ascii"))
        if decoded[:5] == PDF_MAGIC:
            return decoded
    except Exception:
        pass

    # Retorna como está — o chamador decide o que fazer
    return data


# ---------------------------------------------------------------------------
# Conversão PDF/A via Ghostscript
# ---------------------------------------------------------------------------


def convert_to_pdfa(pdf_bytes: bytes) -> tuple[bytes, bool, str]:
    """Converte bytes de um PDF para PDF/A-2 usando Ghostscript.

    Returns:
        (bytes_finais, convertido_ok, mensagem_erro)
        Se a conversão falhar, retorna os bytes originais intactos.
    """
    tmp_in_path = tmp_out_path = None
    try:
        with (
            tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_in,
            tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_out,
        ):
            tmp_in_path  = Path(tmp_in.name)
            tmp_out_path = Path(tmp_out.name)
            tmp_in.write(pdf_bytes)

        cmd    = GS_CMD_BASE + [f"-sOutputFile={tmp_out_path}", str(tmp_in_path)]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=GS_TIMEOUT,
        )

        if result.returncode == 0 and tmp_out_path.stat().st_size > 0:
            return tmp_out_path.read_bytes(), True, ""

        err_msg = (
            result.stderr.decode("utf-8", errors="ignore").strip()
            or f"Código de saída Ghostscript: {result.returncode}"
        )
        return pdf_bytes, False, err_msg

    except Exception as exc:  # noqa: BLE001
        return pdf_bytes, False, str(exc)
    finally:
        for p in (tmp_in_path, tmp_out_path):
            if p and p.exists():
                p.unlink()


# ---------------------------------------------------------------------------
# Processamento de um único anexo
# ---------------------------------------------------------------------------


def process_attachment(
    *,
    publicacao_id: int,
    anexo_id:      int,
    raw_name:      str | None,
    arquivo,
    item_dir:      Path,
    used_names:    set[str],
    stats:         ExtractionStats,
    issues:        list[Issue],
) -> str | None:
    """Decodifica, converte (se PDF) e grava um único anexo no diretório SAF.

    Returns:
        O nome de arquivo gravado, ou None se o anexo foi ignorado.
    """
    # --- Nome de arquivo seguro e único ----------------------------------- #
    safe_name = sanitize_filename(raw_name or f"documento_{anexo_id}.pdf")
    if safe_name in used_names:
        stem, suffix = Path(safe_name).stem, Path(safe_name).suffix or ".pdf"
        safe_name = f"{stem}_{anexo_id}{suffix}"
    used_names.add(safe_name)

    # --- Binário nulo no banco -------------------------------------------- #
    if not arquivo:
        logger.warning(
            "Arquivo binário nulo para publicacao_id=%s, anexo_id=%s (%s) — ignorado.",
            publicacao_id, anexo_id, raw_name,
        )
        stats.skipped_null += 1
        issues.append(Issue(
            publicacao_id=publicacao_id, anexo_id=anexo_id, filename=safe_name,
            issue_type="NULL_BINARY",
            details="Campo binário 'arquivo' está nulo no PostgreSQL",
            action_taken="Ignorado",
        ))
        return None

    try:
        file_bytes = decode_file_bytes(arquivo)

        # --- Decodificação falhou ----------------------------------------- #
        if not file_bytes:
            logger.warning(
                "Falha ao decodificar publicacao_id=%s, anexo_id=%s — ignorado.",
                publicacao_id, anexo_id,
            )
            stats.skipped_null += 1
            issues.append(Issue(
                publicacao_id=publicacao_id, anexo_id=anexo_id, filename=safe_name,
                issue_type="CORRUPT_DECODE_FAILURE",
                details="Falha ao decodificar bytes do arquivo (formato irreconhecível)",
                action_taken="Ignorado",
            ))
            return None

        # --- Decisão: é PDF ou outro formato? ----------------------------- #
        has_pdf_header = file_bytes.startswith(PDF_MAGIC)
        is_pdf_ext     = safe_name.lower().endswith(".pdf")

        if has_pdf_header:
            final_bytes, converted_ok, err_msg = convert_to_pdfa(file_bytes)
            if not converted_ok:
                stats.pdfa_failures += 1
                logger.warning(
                    "Conversão PDF/A falhou em publicacao_id=%s (anexo_id=%s, %s): %s. Salvando PDF original.",
                    publicacao_id, anexo_id, safe_name, err_msg,
                )
                issues.append(Issue(
                    publicacao_id=publicacao_id, anexo_id=anexo_id, filename=safe_name,
                    issue_type="PDFA_CONVERSION_FAILED",
                    details=err_msg,
                    action_taken="Salvo PDF original (sem conformidade PDF/A)",
                ))
            stats.written += 1

        elif is_pdf_ext:
            # Extensão .pdf mas conteúdo inválido — registra e preserva
            stats.pdfa_failures += 1
            logger.warning(
                "Arquivo '%s' (publicacao_id=%s, anexo_id=%s) tem extensão .pdf "
                "mas sem cabeçalho %%PDF- válido. Salvando como está.",
                safe_name, publicacao_id, anexo_id,
            )
            issues.append(Issue(
                publicacao_id=publicacao_id, anexo_id=anexo_id, filename=safe_name,
                issue_type="INVALID_PDF_HEADER",
                details="Extensão .pdf porém conteúdo não possui o cabeçalho %PDF-",
                action_taken="Salvo arquivo original sem conversão PDF/A",
            ))
            final_bytes = file_bytes
            stats.written += 1

        else:
            # Imagem, ZIP, DOCX, etc. — preserva sem conversão
            final_bytes = file_bytes
            stats.non_pdf += 1
            logger.debug(
                "Anexo não-PDF preservado (publicacao_id=%s, anexo_id=%s, %s).",
                publicacao_id, anexo_id, safe_name,
            )

        (item_dir / safe_name).write_bytes(final_bytes)
        logger.debug("Gravado: %s (%d bytes)", item_dir / safe_name, len(final_bytes))
        return safe_name

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Falha ao gravar publicacao_id=%s, anexo=%s: %s — ignorado.",
            publicacao_id, safe_name, exc,
        )
        stats.skipped_null += 1
        issues.append(Issue(
            publicacao_id=publicacao_id, anexo_id=anexo_id, filename=safe_name,
            issue_type="WRITE_FAILED",
            details=str(exc),
            action_taken="Ignorado",
        ))
        return None


# ---------------------------------------------------------------------------
# Limpeza de SAF órfão
# ---------------------------------------------------------------------------


def cleanup_orphaned_contents(saf_bundle_dir: Path) -> None:
    """Remove ou corrige arquivos 'contents' cujos arquivos listados não existem no disco."""
    if not saf_bundle_dir.is_dir():
        return

    cleaned = removed = 0
    for item_dir in saf_bundle_dir.rglob("item_*"):
        contents_file = item_dir / "contents"
        if not contents_file.is_file():
            continue

        lines       = contents_file.read_text(encoding="utf-8").splitlines()
        valid_lines = [
            line.strip()
            for line in lines
            if line.strip()
            and (item_dir / contents_entry_filename(line)).is_file()
        ]

        if valid_lines:
            if len(valid_lines) != len(lines):
                contents_file.write_text("\n".join(valid_lines) + "\n", encoding="utf-8")
                cleaned += 1
        else:
            contents_file.unlink()
            removed += 1

    if cleaned or removed:
        logger.info(
            "Limpeza de 'contents': %d corrigidos, %d removidos.", cleaned, removed
        )


def clear_managed_contents(item_dir: Path) -> None:
    """Remove o manifesto anterior e somente os arquivos que ele gerenciava.

    Isso torna a reextração fiel ao banco: um anexo removido ou marcado com
    ``exibir_pdf=false`` não pode sobreviver em um ``contents`` antigo.
    """
    contents_file = item_dir / "contents"
    if not contents_file.is_file():
        return

    for line in contents_file.read_text(encoding="utf-8").splitlines():
        filename = contents_entry_filename(line)
        if not filename:
            continue
        relative = Path(filename)
        if relative.is_absolute() or len(relative.parts) != 1:
            logger.warning("Entrada insegura ignorada em %s: %s", contents_file, line)
            continue
        managed_file = item_dir / relative
        if managed_file.is_file() or managed_file.is_symlink():
            managed_file.unlink()
    contents_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------


def connect() -> psycopg2.extensions.connection:
    logger.info("Conectando ao banco %s em %s:%s...", DB_NAME, DB_HOST, DB_PORT)
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )


# ---------------------------------------------------------------------------
# Ponto de entrada principal
# ---------------------------------------------------------------------------


def export_issues_csv(issues: list[Issue], path: Path) -> None:
    """Grava o relatório de anomalias em CSV."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ISSUES_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(issue.as_dict() for issue in issues)


# Removido find_item_dir pois o mapeamento é feito no inicio de extract_pdfs


def extract_pdfs(limit: int | None = None) -> None:
    issues: list[Issue] = []
    stats  = ExtractionStats()
    issues_csv_path = Path("pdf_extraction_issues.csv")
    # Evita que um relatório de execução anterior gere um falso alerta.
    export_issues_csv([], issues_csv_path)
    if BATCH_SIZE <= 0:
        raise ValueError("BATCH_SIZE deve ser maior que zero")
    conn   = connect()
    logger.info("Conexão estabelecida com sucesso.")

    try:
        logger.info("Varrendo diretórios SAF gerados para identificar os itens...")
        saf_dirs: dict[int, Path] = {}
        if SAF_BUNDLE_DIR.is_dir():
            for p in SAF_BUNDLE_DIR.rglob("item_*"):
                if p.is_dir():
                    match = re.fullmatch(r"item_(\d+)", p.name)
                    if match is None:
                        continue
                    pub_id = int(match.group(1))
                    if pub_id in saf_dirs and saf_dirs[pub_id] != p:
                        raise RuntimeError(
                            f"Mais de uma pasta SAF encontrada para item_{pub_id}: "
                            f"{saf_dirs[pub_id]} e {p}"
                        )
                    saf_dirs[pub_id] = p

        all_ids = sorted(saf_dirs.keys())
        access_policies = read_access_policies(SAF_BUNDLE_DIR)

        if limit is not None:
            logger.info("Limitando a extração a %d publicações (modo teste).", limit)
            all_ids = all_ids[:limit]

        total = len(all_ids)
        logger.info("Total de publicações únicas (exibir_pdf=%s): %d", EXIBIR_PDF_FILTER, total)
        logger.info("Tamanho do lote: %d publicações", BATCH_SIZE)

        if not all_ids:
            logger.info("Nenhum registro encontrado.")
            cleanup_orphaned_contents(SAF_BUNDLE_DIR)
            return

        chunks = [all_ids[i : i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

        with conn.cursor() as cur:
            for batch_idx, chunk in enumerate(chunks, start=1):
                stats.processed_total += len(chunk)
                logger.info(
                    "Lote %d/%d — publicações %s a %s [%d/%d]",
                    batch_idx, len(chunks), chunk[0], chunk[-1],
                    stats.processed_total, total,
                )

                cur.execute(BATCH_BINARY_QUERY, {"id_list": chunk, "exibir_pdf": EXIBIR_PDF_FILTER})
                pub_attachments: dict[int, list] = defaultdict(list)
                for pub_id, anx_id, name, arquivo in cur.fetchall():
                    pub_attachments[pub_id].append((anx_id, name, arquivo))

                for publicacao_id in chunk:
                    item_dir    = saf_dirs.get(publicacao_id)
                    attachments = pub_attachments.get(publicacao_id, [])

                    if item_dir is None:
                        logger.warning("Pasta SAF não encontrada para publicacao_id=%s.", publicacao_id)
                        stats.skipped_nodir += 1
                        issues.append(Issue(
                            publicacao_id=publicacao_id, anexo_id="-", filename="-",
                            issue_type="MISSING_SAF_DIRECTORY",
                            details=f"Diretório 'item_{publicacao_id}' não foi encontrado recursivamente no disco",
                            action_taken="Ignorado",
                        ))
                        continue

                    clear_managed_contents(item_dir)

                    if not attachments:
                        logger.warning("Nenhum anexo para publicacao_id=%s — ignorado.", publicacao_id)
                        stats.skipped_null += 1
                        issues.append(Issue(
                            publicacao_id=publicacao_id, anexo_id="-", filename="-",
                            issue_type="NO_ATTACHMENT_RECORD",
                            details="Nenhum anexo encontrado no banco para esta publicação",
                            action_taken="Ignorado",
                        ))
                        continue

                    if len(attachments) > 1:
                        stats.multi_attachment_pubs += 1

                    used_names:     set[str]  = set()
                    contents_lines: list[str] = []
                    access_policy = access_policies.get(publicacao_id)

                    for anexo_id, raw_name, arquivo in attachments:
                        saved = process_attachment(
                            publicacao_id=publicacao_id,
                            anexo_id=anexo_id,
                            raw_name=raw_name,
                            arquivo=arquivo,
                            item_dir=item_dir,
                            used_names=used_names,
                            stats=stats,
                            issues=issues,
                        )
                        if saved:
                            contents_lines.append(
                                build_contents_entry(saved, access_policy)
                            )

                    if contents_lines:
                        (item_dir / "contents").write_text(
                            "\n".join(contents_lines) + "\n", encoding="utf-8"
                        )

        cleanup_orphaned_contents(SAF_BUNDLE_DIR)

        # --- Relatório de anomalias --------------------------------------- #
        export_issues_csv(issues, issues_csv_path)

        # --- Resumo ------------------------------------------------------- #
        SEP = "=" * 70
        logger.info(SEP)
        logger.info("  RESUMO DA EXTRAÇÃO DE ANEXOS")
        logger.info(SEP)
        logger.info("  ✔ PDFs gravados com sucesso            : %d", stats.written)
        logger.info("  🖼  Outros anexos preservados (não-PDF) : %d", stats.non_pdf)
        logger.info("  📎 Publicações com múltiplos anexos    : %d", stats.multi_attachment_pubs)
        logger.info("  ⚠  Falhas de conversão PDF/A           : %d", stats.pdfa_failures)
        logger.info("  ✘ Pastas SAF inexistentes              : %d", stats.skipped_nodir)
        logger.info("  ✘ Binários nulos ou corrompidos        : %d", stats.skipped_null)
        logger.info(SEP)

        if issues:
            logger.warning(SEP)
            logger.warning("  ⚠️  ATENÇÃO: %d ANOMALIAS ENCONTRADAS!", len(issues))
            logger.warning("  Relatório exportado para: %s", issues_csv_path.resolve())
            logger.warning(SEP)

    finally:
        conn.close()
        logger.info("Conexão com o banco encerrada.")
