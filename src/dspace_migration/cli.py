import sys
from pathlib import Path
from dspace_migration.metadata import process_data
from dspace_migration.pdfs import extract_pdfs
from dspace_migration.organization import setup_dspace, generate_import_script


def check_and_report_issues():
    """Verifica e exibe alertas caso existam relatórios de anomalias/erros gerados."""
    issues_csv = Path("pdf_extraction_issues.csv")
    embargo_csv = Path("embargoed_items.csv")
    routing_csv = Path("routing_report.csv")

    has_alerts = False

    print()
    print("======================================================================")
    print("                RELATÓRIO AUDITORIA FINAL DA MIGRAÇÃO                 ")
    print("======================================================================")

    if embargo_csv.exists():
        lines = embargo_csv.read_text(encoding="utf-8").splitlines()
        count = max(0, len(lines) - 1)
        if count > 0:
            print(f"  🔒 Itens com Restrição/Embargo de Acesso: {count}")
            print(f"     ➔ Consulte o arquivo: {embargo_csv.resolve()}")

    if routing_csv.exists():
        lines = routing_csv.read_text(encoding="utf-8").splitlines()
        unmapped = sum(1 for line in lines if ",UNMAPPED" in line)
        if unmapped > 0:
            has_alerts = True
            print(f"\n  ⚠️  Publicações sem mapeamento de curso: {unmapped}")
            print(f"     ➔ Consulte o relatório: {routing_csv.resolve()}")

    if issues_csv.exists():
        lines = issues_csv.read_text(encoding="utf-8").splitlines()
        count = max(0, len(lines) - 1)
        if count > 0:
            has_alerts = True
            print(f"\n  ⚠️  ALERTAS/ANOMALIAS DE PDFS DETECTADOS: {count} registro(s)")
            print(f"     ➔ Consulte o relatório detalhado em: {issues_csv.resolve()}")

    if not has_alerts:
        print("  ✔ Nenhum erro crítico detectado.")

    print("======================================================================")


def run_extract_metadata():
    """CLI command to extract metadata and build SAF structure."""
    print("=== [1/2] Extraindo Metadados e Gerando SAF ===")
    try:
        process_data()
    except Exception as e:
        print(f"✘ Erro fatal na extração de metadados: {e}", file=sys.stderr)
        sys.exit(1)


def run_extract_pdfs():
    """CLI command to extract binary PDF files into SAF directories."""
    print("=== [2/2] Extraindo Arquivos PDF Binários ===")
    try:
        extract_pdfs()
    except Exception as e:
        print(f"✘ Erro fatal na extração de PDFs: {e}", file=sys.stderr)
        sys.exit(1)


def run_setup_dspace():
    """CLI command to create community/collection hierarchy in DSpace via REST API."""
    print("=== Configurando Hierarquia de Comunidades/Coleções no DSpace ===")
    try:
        result = setup_dspace()
        if result:
            print(f"✔ {len(result)} coleções processadas. UUIDs salvos em collection_uuids.json")
        else:
            print("✘ Nenhuma coleção processada. Verifique os logs.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"✘ Erro fatal ao configurar DSpace: {e}", file=sys.stderr)
        sys.exit(1)


def run_generate_import_script():
    """CLI command to generate per-collection import shell script."""
    print("=== Gerando Script de Importação por Coleção ===")
    try:
        generate_import_script()
        print("✔ Script import_all.sh gerado com sucesso.")
    except Exception as e:
        print(f"✘ Erro fatal ao gerar script: {e}", file=sys.stderr)
        sys.exit(1)


def migrate_all():
    """CLI command to run the full migration pipeline."""
    print("==================================================")
    print("    Iniciando Pipeline Completo de Migração      ")
    print("==================================================")
    run_extract_metadata()
    print()
    run_extract_pdfs()
    check_and_report_issues()


if __name__ == "__main__":
    migrate_all()
