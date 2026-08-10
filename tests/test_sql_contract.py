import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class MetadataSqlContractTests(unittest.TestCase):
    def test_query_exposes_every_pipeline_control_column(self):
        query = (PROJECT_ROOT / "sql" / "extract_metadata.sql").read_text(
            encoding="utf-8"
        )

        for alias in (
            "id_origem",
            "data_limite_embargo",
            "autorizar_publicacao",
            "curso_nome",
        ):
            with self.subTest(alias=alias):
                self.assertIn(f'AS "{alias}"', query)

        self.assertIn("ORDER BY p.id", query)


if __name__ == "__main__":
    unittest.main()
