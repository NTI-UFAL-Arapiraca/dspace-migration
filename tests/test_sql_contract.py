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
            "pessoas",
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

    def test_academic_fields_have_explicit_names(self):
        query = (PROJECT_ROOT / "sql/extract_metadata.sql").read_text()
        self.assertIn('c.name AS "local.course.name"', query)
        self.assertIn('camp.name AS "local.campus.name"', query)
        self.assertNotIn('AS "dc.description.degree"', query)
        self.assertNotIn('AS "dc.publisher.department"', query)
        self.assertIn("'source', 'ud_biblioteca_publicacao_autor'", query)
        self.assertIn("'source', 'ud_biblioteca_publicacao_orientador'", query)

    def test_query_maps_publication_year_and_defense_date_separately(self):
        query = (PROJECT_ROOT / "sql" / "extract_metadata.sql").read_text(
            encoding="utf-8"
        )

        self.assertIn('p.ano_pub AS "dc.date.issued"', query)
        self.assertIn('p.data_defesa AS "local.date.defense"', query)
        self.assertNotIn('AS "dc.date.submitted"', query)
        self.assertNotIn('p.data_defesa AS "dc.date.issued"', query)

    def test_query_extracts_cnpq_categories_as_separate_local_values(self):
        query = (PROJECT_ROOT / "sql" / "extract_metadata.sql").read_text(
            encoding="utf-8"
        )

        self.assertIn("FROM categoria_cnpq_ids cci", query)
        self.assertIn('AS "local.cnpq.area"', query)


if __name__ == "__main__":
    unittest.main()
