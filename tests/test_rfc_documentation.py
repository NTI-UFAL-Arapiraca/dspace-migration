import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RFC_ROOT = PROJECT_ROOT / "docs/rfc"


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
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        import_guide = (PROJECT_ROOT / "docs/3_importacao_dspace.md").read_text(
            encoding="utf-8"
        )

        for content in (readme, import_guide):
            with self.subTest(document=content[:40]):
                self.assertIn("Migração das Estatísticas de Acesso", content)
                self.assertIn("ud_biblioteca_publicacao.visualizacoes", content)
                self.assertIn("mapfile.txt", content)
                self.assertIn("uv run inject-stats --dry-run", content)
                self.assertIn("SOLR_BATCH_SIZE", content)
                self.assertIn("determinísticos", content)


if __name__ == "__main__":
    unittest.main()
