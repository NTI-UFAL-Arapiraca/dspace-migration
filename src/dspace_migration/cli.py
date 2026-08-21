import sys
import argparse
import subprocess
from pathlib import Path
from dspace_migration.metadata import process_data
from dspace_migration.pdfs import extract_pdfs
from dspace_migration.embargoes import apply_embargoes
from dspace_migration.organization import setup_dspace, generate_import_script
from dspace_migration.statistics import inject_statistics


def check_and_report_issues():
    """Verifica e exibe alertas caso existam relatórios de anomalias/erros gerados."""
    issues_csv = Path("pdf_extraction_issues.csv")
    routing_csv = Path("routing_report.csv")

    has_alerts = False

    print()
    print("======================================================================")
    print("                RELATÓRIO AUDITORIA FINAL DA MIGRAÇÃO                 ")
    print("======================================================================")

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
    parser = argparse.ArgumentParser(description="Extrai metadados e gera pacotes SAF.")
    parser.add_argument("--limit", type=int, default=None, help="Limita o número de itens processados (para testes)")
    
    # We use parse_known_args in case this is called from migrate_all or other contexts with extra args
    args, _ = parser.parse_known_args()

    print("=== [1/2] Extraindo Metadados e Gerando SAF ===")
    try:
        process_data(limit=args.limit)
    except Exception as e:
        print(f"✘ Erro fatal na extração de metadados: {e}", file=sys.stderr)
        sys.exit(1)


def run_extract_pdfs():
    """CLI command to extract binary PDF files into SAF directories."""
    parser = argparse.ArgumentParser(description="Extrai arquivos PDF binários.")
    parser.add_argument("--limit", type=int, default=None, help="Limita o número de itens processados (para testes)")
    
    # We use parse_known_args in case this is called from migrate_all or other contexts with extra args
    args, _ = parser.parse_known_args()

    print("=== [2/2] Extraindo Arquivos PDF Binários ===")
    try:
        extract_pdfs(limit=args.limit)
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


def run_apply_embargoes():
    """CLI command to apply embargo release dates after the SAF import."""
    parser = argparse.ArgumentParser(
        description="Aplica no DSpace as datas de liberação dos PDFs embargados."
    )
    parser.add_argument(
        "--saf-bundle-dir",
        default=None,
        help="Caminho para o SAF bundle (default: SAF_BUNDLE_DIR do .env)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Não altera o DSpace")
    args, _ = parser.parse_known_args()

    print("=== Aplicando Embargos no DSpace ===")
    try:
        result = apply_embargoes(
            saf_bundle_dir=args.saf_bundle_dir,
            dry_run=args.dry_run,
        )
        print(
            f"✔ {result.items} item(ns) embargado(s), "
            f"{result.bitstreams} bitstream(s) verificado(s)."
        )
    except Exception as e:
        print(f"✘ Erro fatal ao aplicar embargos: {e}", file=sys.stderr)
        sys.exit(1)


def run_inject_stats():
    """CLI command to inject historical view counts into DSpace Solr statistics core."""
    parser = argparse.ArgumentParser(
        description="Injeta contagens de visualizações do banco de origem no Solr do DSpace."
    )
    parser.add_argument(
        "--saf-bundle-dir",
        default=None,
        help="Caminho para o SAF bundle (default: SAF_BUNDLE_DIR do .env)",
    )
    parser.add_argument(
        "--solr-url",
        default=None,
        help="URL base do Solr (default: SOLR_URL do .env, ex: http://localhost:8983/solr)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula o processo sem enviar dados ao Solr",
    )
    args, _ = parser.parse_known_args()

    print("=== Injetando Estatísticas de Visualizações no DSpace ===")
    try:
        inject_statistics(
            saf_bundle_dir=args.saf_bundle_dir,
            solr_url=args.solr_url,
            dry_run=args.dry_run,
        )
    except FileNotFoundError as e:
        print(f"✘ Erro: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✘ Erro fatal ao injetar estatísticas: {e}", file=sys.stderr)
        sys.exit(1)


def rebuild_oai_index(docker_container: str = "dspace") -> None:
    """Clear and rebuild the OAI Solr index using the running DSpace backend."""
    command = [
        "docker",
        "exec",
        docker_container,
        "/dspace/bin/dspace",
        "oai",
        "import",
        "-c",
    ]
    print(f"  → {' '.join(command)}")
    subprocess.run(command, check=True)


def run_rebuild_oai():
    """CLI command to rebuild the DSpace OAI-PMH index."""
    parser = argparse.ArgumentParser(
        description="Limpa e reconstrói o índice OAI-PMH do DSpace."
    )
    parser.add_argument(
        "--docker-container",
        default="dspace",
        help="Nome do container Docker do DSpace (default: dspace)",
    )
    args, _ = parser.parse_known_args()

    print("=== Reconstruindo Índice OAI-PMH do DSpace ===")
    try:
        rebuild_oai_index(args.docker_container)
        print("✔ Índice OAI-PMH reconstruído.")
    except subprocess.CalledProcessError as e:
        print(
            f"✘ Erro ao reconstruir o índice OAI (exit code {e.returncode}).",
            file=sys.stderr,
        )
        sys.exit(1)
    except FileNotFoundError:
        print(
            "✘ Comando 'docker' não encontrado. Verifique se o Docker está instalado.",
            file=sys.stderr,
        )
        sys.exit(1)


def migrate_all():
    """CLI command to run the full end-to-end migration pipeline."""
    parser = argparse.ArgumentParser(description="Pipeline completo de migração para o DSpace.")
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Pula a etapa de importação SAF no Docker (útil se já foi importado)",
    )
    parser.add_argument(
        "--skip-stats",
        action="store_true",
        help="Pula a injeção de estatísticas no Solr",
    )
    parser.add_argument(
        "--skip-oai",
        action="store_true",
        help="Pula a reconstrução do índice OAI-PMH",
    )
    parser.add_argument(
        "--docker-container",
        default="dspace",
        help="Nome do container Docker do DSpace (default: dspace)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limita o número de itens processados nas etapas de extração (para testes)",
    )
    args, _ = parser.parse_known_args()

    total_steps = (
        5
        + int(not args.skip_docker)
        + int(not args.skip_stats)
        + int(not args.skip_oai)
    )
    step = 1

    print("══════════════════════════════════════════════════")
    print("       Pipeline Completo de Migração DSpace       ")
    print("══════════════════════════════════════════════════")

    # ── Etapa 1: Metadados + SAF ──────────────────────────────────────────────
    print(f"\n[{step}/{total_steps}] Extraindo metadados e gerando SAF...")
    step += 1
    try:
        process_data(limit=args.limit)
    except Exception as e:
        print(f"✘ Erro fatal na extração de metadados: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Etapa 2: PDFs ────────────────────────────────────────────────────────
    print(f"\n[{step}/{total_steps}] Extraindo arquivos PDF...")
    step += 1
    try:
        extract_pdfs(limit=args.limit)
    except Exception as e:
        print(f"✘ Erro fatal na extração de PDFs: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Etapa 3: Hierarquia DSpace ────────────────────────────────────────────
    print(f"\n[{step}/{total_steps}] Configurando hierarquia de comunidades/coleções no DSpace...")
    step += 1
    try:
        result = setup_dspace()
        if not result:
            print("✘ Falha ao configurar hierarquia DSpace.", file=sys.stderr)
            sys.exit(1)
        print(f"  ✔ {len(result)} coleções processadas.")
    except Exception as e:
        print(f"✘ Erro fatal ao configurar DSpace: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Etapa 4: Gerar script de importação ──────────────────────────────────
    print(f"\n[{step}/{total_steps}] Gerando script de importação (import_all.sh)...")
    step += 1
    try:
        generate_import_script()
        print("  ✔ import_all.sh gerado.")
    except Exception as e:
        print(f"✘ Erro fatal ao gerar script de importação: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Etapa 5: Importação SAF no Docker ────────────────────────────────────
    if not args.skip_docker:
        container = args.docker_container
        print(f"\n[{step}/{total_steps}] Executando importação SAF no container '{container}'...")
        step += 1
        try:
            # Copia o script para dentro do container
            cp_cmd = ["docker", "cp", "import_all.sh", f"{container}:/dspace/import_all.sh"]
            print(f"  → docker cp import_all.sh {container}:/dspace/import_all.sh")
            subprocess.run(cp_cmd, check=True)

            # Executa o script dentro do container (streaming de output)
            exec_cmd = ["docker", "exec", container, "bash", "/dspace/import_all.sh"]
            print(f"  → docker exec {container} bash /dspace/import_all.sh\n")
            subprocess.run(exec_cmd, check=True)
            print("  ✔ Importação SAF concluída.")
        except subprocess.CalledProcessError as e:
            print(f"✘ Erro durante a importação no Docker (exit code {e.returncode}).", file=sys.stderr)
            print("  Verifique se o container está rodando e o volume do SAF bundle está montado.", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError:
            print("✘ Comando 'docker' não encontrado. Verifique se o Docker está instalado.", file=sys.stderr)
            sys.exit(1)
    else:
        print("\nImportação SAF no Docker: PULADA (--skip-docker)")

    # ── Aplicar datas de liberação dos embargos ────────────────────────
    print(f"\n[{step}/{total_steps}] Aplicando políticas de embargo no DSpace...")
    step += 1
    try:
        result = apply_embargoes()
        print(
            f"  ✔ {result.items} item(ns) embargado(s), "
            f"{result.bitstreams} bitstream(s) verificado(s)."
        )
    except Exception as e:
        print(f"✘ Erro fatal ao aplicar embargos: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Etapa 6: Injeção de estatísticas ─────────────────────────────────────
    if not args.skip_stats:
        print(f"\n[{step}/{total_steps}] Injetando estatísticas de visualizações no Solr...")
        step += 1
        try:
            inject_statistics()
            print("  ✔ Estatísticas injetadas.")
        except Exception as e:
            print(f"✘ Erro fatal ao injetar estatísticas: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("\nInjeção de estatísticas: PULADA (--skip-stats)")

    # ── Reconstrução do índice OAI-PMH ──────────────────────────────────────
    if not args.skip_oai:
        print(f"\n[{step}/{total_steps}] Reconstruindo índice OAI-PMH...")
        try:
            rebuild_oai_index(args.docker_container)
            print("  ✔ Índice OAI-PMH reconstruído.")
        except subprocess.CalledProcessError as e:
            print(
                f"✘ Erro ao reconstruir o índice OAI (exit code {e.returncode}).",
                file=sys.stderr,
            )
            sys.exit(1)
        except FileNotFoundError:
            print(
                "✘ Comando 'docker' não encontrado. Verifique se o Docker está instalado.",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        print("\nReconstrução do índice OAI: PULADA (--skip-oai)")

    # ── Relatório final ───────────────────────────────────────────────────────
    check_and_report_issues()
    print("\n══════════════════════════════════════════════════")
    print("  ✔ Pipeline de migração concluído com sucesso!  ")
    print("══════════════════════════════════════════════════\n")


if __name__ == "__main__":
    migrate_all()
