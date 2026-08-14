import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCKER_ROOT = PROJECT_ROOT / "dspace-docker"
SUBMISSION_FORMS = DOCKER_ROOT / "backend/config/submission-forms.xml"


class BackendConfigurationTests(unittest.TestCase):
    def test_compose_mounts_submission_forms_in_rest_and_cli(self):
        expected_mount = (
            "./backend/config/submission-forms.xml:"
            "/dspace/config/submission-forms.xml:ro"
        )

        for compose_file in ("docker-compose-rest.yml", "cli.yml"):
            with self.subTest(compose_file=compose_file):
                compose = (DOCKER_ROOT / compose_file).read_text(encoding="utf-8")
                self.assertIn(expected_mount, compose)

    def test_rest_compose_mounts_configurable_saf_bundle(self):
        compose = (DOCKER_ROOT / "docker-compose-rest.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            (
                "${DSPACE_SAF_HOST_DIR:-${SAF_BUNDLE_DIR:-../saf_bundle}}:"
                "/dspace/saf_bundle"
            ),
            compose,
        )
        self.assertNotIn("/mnt/part2/saf_bundle", compose)

    def test_every_abstract_field_is_repeatable_and_language_qualified(self):
        root = ET.parse(SUBMISSION_FORMS).getroot()
        configured_forms = []

        for form in root.findall("./form-definitions/form"):
            for field in form.findall("./row/field"):
                field_name = (
                    field.findtext("dc-schema"),
                    field.findtext("dc-element"),
                    field.findtext("dc-qualifier"),
                )
                if field_name == ("dc", "description", "abstract"):
                    configured_forms.append(form.attrib["name"])
                    self.assertEqual("true", field.findtext("repeatable"))
                    language = field.find("language")
                    self.assertIsNotNone(language)
                    self.assertEqual("true", language.text)
                    self.assertEqual(
                        "common_iso_languages",
                        language.attrib.get("value-pairs-name"),
                    )

        self.assertEqual(
            ["traditionalpagetwo", "openairePublicationPagetwoForm"],
            configured_forms,
        )

    def test_language_selector_contains_migration_language_codes(self):
        root = ET.parse(SUBMISSION_FORMS).getroot()
        languages = root.find(
            "./form-value-pairs/value-pairs[@value-pairs-name='common_iso_languages']"
        )
        self.assertIsNotNone(languages)
        stored_values = {
            pair.findtext("stored-value") for pair in languages.findall("pair")
        }

        self.assertIn("pt_BR", stored_values)
        self.assertIn("en", stored_values)


if __name__ == "__main__":
    unittest.main()
