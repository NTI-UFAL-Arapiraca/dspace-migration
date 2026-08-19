import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from dspace_migration.access import read_access_policies
from dspace_migration.metadata import process_data


class MetadataPipelineTests(unittest.TestCase):
    def _dataframe(self):
        return pd.DataFrame([{
            "id_origem": 42,
            "dc.title": "<b>Trabalho</b> &amp; pesquisa",
            "dc.title.alternative": "Abstract",
            "dc.description.abstract[pt]": "<i>Mesmo resumo</i>",
            "dc.description.abstract[en]": "<i>Mesmo resumo</i>",
            "dc.date.issued": "2024-05-03",
            # Simula uma consulta antiga/personalizada: o pipeline deve
            # descartar este campo gerenciado internamente pelo DSpace.
            "dc.date.submitted": "2024-05-04",
            "dc.format.extent": 25,
            "dc.description.note": "Exemplar disponível na biblioteca",
            "dc.identifier.citation": "Exemplar disponível na biblioteca",
            "data_limite_embargo": "2099-01-01",
            "autorizar_publicacao": True,
            "dc.type": "TCC",
            "dc.description.degree": "Curso Teste",
            "dc.publisher.department": "Campus Teste",
            "curso_nome": "Curso Teste",
            "dc.contributor.author": "Silva, Ana||Souza, Beto",
            "dc.contributor.advisor": None,
            "dc.contributor.coadvisor": None,
            "dc.contributor.referee": "Lima, Carla||Melo, Daniel",
            "dc.subject": "Dados||Migração",
        }])

    def test_generates_clean_deduplicated_and_routed_saf_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saf = root / "saf"
            legacy_embargo_csv = root / "embargoed_items.csv"
            legacy_embargo_csv.write_text("relatório antigo", encoding="utf-8")
            sql_file = root / "query.sql"
            sql_file.write_text("SELECT 1", encoding="utf-8")
            old_cwd = Path.cwd()
            os.chdir(root)
            try:
                with (
                    patch(
                        "dspace_migration.metadata.fetch_data_from_db",
                        return_value=self._dataframe(),
                    ),
                    patch(
                        "dspace_migration.metadata.load_curso_mapping",
                        return_value={
                            "Curso Teste": {
                                "old_name": "Curso Teste",
                                "new_path": "Raiz > Polo > Coleção",
                            }
                        },
                    ),
                ):
                    process_data(
                        sql_file=sql_file,
                        saf_bundle_dir=saf,
                    )
            finally:
                os.chdir(old_cwd)

            item = saf / "Polo" / "Coleção" / "item_42"
            xml_root = ET.parse(item / "dublin_core.xml").getroot()
            values = [
                (
                    node.attrib["element"],
                    node.attrib["qualifier"],
                    node.attrib.get("language"),
                    node.text,
                )
                for node in xml_root.findall("dcvalue")
            ]

            self.assertIn(("title", "none", None, "Trabalho & pesquisa"), values)
            self.assertIn(
                ("description", "abstract", "pt", "Mesmo resumo"), values
            )
            self.assertNotIn(
                ("description", "abstract", "en", "Mesmo resumo"), values
            )
            self.assertNotIn(("title", "alternative", None, "Abstract"), values)
            self.assertIn(("date", "issued", None, "2024-05-03"), values)
            self.assertFalse(
                any(element == "date" and qualifier == "submitted"
                    for element, qualifier, _, _ in values)
            )
            self.assertIn(("language", "iso", None, "pt_BR"), values)
            self.assertIn(
                ("description", "note", None, "Exemplar disponível na biblioteca"),
                values,
            )
            self.assertFalse(
                any(element == "identifier" and qualifier == "citation"
                    for element, qualifier, _, _ in values)
            )
            self.assertEqual(
                ["Silva, Ana", "Souza, Beto"],
                [value for element, qualifier, _, value in values
                 if (element, qualifier) == ("contributor", "author")],
            )
            self.assertEqual(
                ["Lima, Carla", "Melo, Daniel"],
                [value for element, qualifier, _, value in values
                 if (element, qualifier) == ("contributor", "referee")],
            )
            self.assertEqual("embargo", read_access_policies(saf)[42].access_type)
            self.assertFalse(legacy_embargo_csv.exists())


if __name__ == "__main__":
    unittest.main()
