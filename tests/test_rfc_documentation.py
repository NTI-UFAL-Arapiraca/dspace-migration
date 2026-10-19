import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEPLOYMENT_ROOT = PROJECT_ROOT / "dspace-docker"
if not DEPLOYMENT_ROOT.exists():
    DEPLOYMENT_ROOT = PROJECT_ROOT.parent / "dspace-bca"
RFC_ROOT = DEPLOYMENT_ROOT / "rfc"


class RfcDocumentationTests(unittest.TestCase):
    EXPECTED_RFCS = {
        "0001-build-e-ativacao-do-tema-custom.md",
        "0002-remocao-do-banner-promocional.md",
        "0003-idioma-anonimo-padrao-pt-br.md",
        "0004-metadados-academicos-na-pagina-do-item.md",
        "0005-formatacao-localizada-da-data.md",
        "0006-alinhamento-justificado-do-resumo.md",
        "0007-negociacao-de-idioma-dos-metadados.md",
        "0008-formulario-de-resumos-multilingues.md",
        "0009-ocultacao-de-notas-internas.md",
        "0010-nome-publico-do-repositorio.md",
        "0011-endpoint-oai-pmh.md",
        "0012-seo-sitemaps-robots-ssr.md",
        "0013-banco-geoip-geolite2.md",
        "0014-pessoas-e-metadados-academicos.md",
    }

    def test_every_known_override_has_an_indexed_rfc(self):
        index = (RFC_ROOT / "README.md").read_text(encoding="utf-8")
        actual_rfcs = {path.name for path in RFC_ROOT.glob("[0-9][0-9][0-9][0-9]-*.md")}

        self.assertEqual(self.EXPECTED_RFCS, actual_rfcs)
        for filename in self.EXPECTED_RFCS:
            with self.subTest(filename=filename):
                self.assertIn(f"({filename})", index)

    def test_each_rfc_records_decision_implementation_and_validation(self):
        required_sections = (
            "- Status:",
            "- Escopo:",
            "## Contexto",
            "## Decisão",
            "## Implementação",
            "## Consequências e validação",
        )

        for filename in self.EXPECTED_RFCS:
            with self.subTest(filename=filename):
                content = (RFC_ROOT / filename).read_text(encoding="utf-8")
                for section in required_sections:
                    self.assertIn(section, content)

    def test_access_statistics_migration_is_documented(self):
        reference = (PROJECT_ROOT / "docs/referencia/estatisticas.md").read_text(
            encoding="utf-8"
        )
        guide = (PROJECT_ROOT / "docs/guias/estatisticas.md").read_text(
            encoding="utf-8"
        )
        for topic in ("Migração das Estatísticas de Acesso",
                      "ud_biblioteca_publicacao.visualizacoes", "mapfile.txt",
                      "SOLR_BATCH_SIZE", "determinísticos"):
            self.assertIn(topic, reference)
        self.assertIn("uv run inject-stats --dry-run", guide)
        self.assertIn("uv run inject-stats", guide)

    def test_seo_and_oai_maintenance_is_documented(self):
        guide = (PROJECT_ROOT / "docs/guias/operacao.md").read_text(
            encoding="utf-8"
        )

        required_topics = (
            "DSPACE_SERVER_URL",
            "DSPACE_UI_URL",
            "X-Forwarded-Proto",
            "uv run generate-sitemaps",
            "frontend/overrides/robots.txt.ejs",
            "/app/dist/server/main.js",
            "uv run rebuild-oai",
            "docker compose down -v",
            "Checklist após migração ou manutenção",
        )
        for topic in required_topics:
            self.assertIn(topic, guide)


if __name__ == "__main__":
    unittest.main()
