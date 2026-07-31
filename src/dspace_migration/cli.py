import sys
from dspace_migration.metadata import process_data
from dspace_migration.pdfs import extract_pdfs


def run_extract_metadata():
    """CLI command to extract metadata and build SAF structure."""
    print("=== [1/2] Extraindo Metadados e Gerando SAF ===")
    try:
        process_data()
    except Exception as e:
        print(f"Erro na extração de metadados: {e}", file=sys.stderr)
        sys.exit(1)


def run_extract_pdfs():
    """CLI command to extract binary PDF files into SAF directories."""
    print("=== [2/2] Extraindo Arquivos PDF Binários ===")
    try:
        extract_pdfs()
    except Exception as e:
        print(f"Erro na extração de PDFs: {e}", file=sys.stderr)
        sys.exit(1)


def migrate_all():
    """CLI command to run both metadata processing and PDF extraction in sequence."""
    print("==================================================")
    print("    Iniciando Pipeline Completo de Migração      ")
    print("==================================================")
    run_extract_metadata()
    print()
    run_extract_pdfs()
    print("==================================================")
    print("       Migração concluída com sucesso!            ")
    print("==================================================")


if __name__ == "__main__":
    migrate_all()
