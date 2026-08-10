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

    def test_query_extracts_referees_from_examination_board_relation(self):
        query = (PROJECT_ROOT / "sql" / "extract_metadata.sql").read_text(
            encoding="utf-8"
        )

        self.assertIn("FROM publicacao_membro_banca_rel", query)
        self.assertIn("pmb.ud_biblioteca_publicacao_id = p.id", query)
        self.assertIn('AS "dc.contributor.referee"', query)

    def test_query_maps_defense_date_only_to_date_issued(self):
        query = (PROJECT_ROOT / "sql" / "extract_metadata.sql").read_text(
            encoding="utf-8"
        )

        self.assertIn('p.data_defesa AS "dc.date.issued"', query)
        self.assertNotIn('AS "dc.date.submitted"', query)


if __name__ == "__main__":
    unittest.main()
