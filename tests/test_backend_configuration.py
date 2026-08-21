import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCKER_ROOT = PROJECT_ROOT / "dspace-docker"
SUBMISSION_FORMS = DOCKER_ROOT / "backend/config/submission-forms.xml"
ABSTRACT_LANGUAGE_MIGRATION = (
    DOCKER_ROOT / "backend/sql/normalize_abstract_languages.sql"
)


class BackendConfigurationTests(unittest.TestCase):
    def test_all_official_images_default_to_latest_dspace_10_line(self):
        rest_compose = (DOCKER_ROOT / "docker-compose-rest.yml").read_text(
            encoding="utf-8"
        )
        cli_compose = (DOCKER_ROOT / "cli.yml").read_text(encoding="utf-8")
        frontend_compose = (DOCKER_ROOT / "docker-compose-dist.yml").read_text(
            encoding="utf-8"
        )
        dockerfile = (DOCKER_ROOT / "Dockerfile.angular").read_text(
            encoding="utf-8"
        )

        self.assertIn("dspace:${DSPACE_VER:-dspace-10_x}", rest_compose)
        self.assertIn("dspace-solr:${DSPACE_VER:-dspace-10_x}", rest_compose)
        self.assertIn("dspace-cli:${DSPACE_VER:-dspace-10_x}", cli_compose)
        self.assertEqual(2, frontend_compose.count("${DSPACE_ANGULAR_TAG:-dspace-10_x}"))
        self.assertIn("ARG DSPACE_ANGULAR_TAG=dspace-10_x", dockerfile)

        all_dspace_config = "\n".join(
            (rest_compose, cli_compose, frontend_compose, dockerfile)
        )
        self.assertNotIn("latest-test", all_dspace_config)
        self.assertNotIn("DSPACE_VER:-latest", all_dspace_config)

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

    def test_rest_negotiates_public_metadata_language(self):
        compose = (DOCKER_ROOT / "docker-compose-rest.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("default__P__locale: ${DSPACE_DEFAULT_LOCALE:-pt_BR}", compose)
        self.assertIn(
            "webui__P__supported__P__locales: "
            "${DSPACE_SUPPORTED_LOCALES:-pt_BR, en}",
            compose,
        )

    def test_public_repository_name_is_institutional_and_configurable(self):
        compose = (DOCKER_ROOT / "docker-compose-rest.yml").read_text(
            encoding="utf-8"
        )
        env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn(
            "dspace__P__name: "
            "${DSPACE_NAME:-Repositório Institucional da UFAL}",
            compose,
        )
        self.assertIn(
            "DSPACE_NAME=Repositório Institucional da UFAL",
            env_example,
        )
        self.assertNotIn("DSpace Started with Docker Compose", compose)

    def test_oai_endpoint_is_enabled_and_uses_public_backend_configuration(self):
        compose = (DOCKER_ROOT / "docker-compose-rest.yml").read_text(
            encoding="utf-8"
        )
        env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

        expected_compose_settings = (
            "dspace__P__server__P__url: "
            "${DSPACE_SERVER_URL:-http://localhost:8080/server}",
            "dspace__P__ui__P__url: ${DSPACE_UI_URL:-http://localhost:4000}",
            "mail__P__admin: "
            "${DSPACE_ADMIN_EMAIL:-${DSPACE_API_USER:-test@test.edu}}",
            'oai__P__enabled: "${OAI_ENABLED:-true}"',
            "oai__P__path: ${OAI_PATH:-oai}",
        )
        for setting in expected_compose_settings:
            self.assertIn(setting, compose)

        expected_env_settings = (
            "DSPACE_SERVER_URL=http://localhost:8080/server",
            "DSPACE_UI_URL=http://localhost:4000",
            "DSPACE_ADMIN_EMAIL=test@test.edu",
            "OAI_ENABLED=true",
            "OAI_PATH=oai",
        )
        for setting in expected_env_settings:
            self.assertIn(setting, env_example)

    def test_sitemaps_are_scheduled_and_persisted(self):
        compose = (DOCKER_ROOT / "docker-compose-rest.yml").read_text(
            encoding="utf-8"
        )
        env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn(
            'sitemap__P__cron: "${SITEMAP_CRON:-0 15 1 * * ?}"',
            compose,
        )
        self.assertIn("- sitemaps:/dspace/sitemaps", compose)
        self.assertIn("  sitemaps:", compose)
        self.assertIn("SITEMAP_CRON=0 15 1 * * ?", env_example)

    def test_existing_abstract_language_migration_is_narrow_and_idempotent(self):
        sql = ABSTRACT_LANGUAGE_MIGRATION.read_text(encoding="utf-8")

        self.assertIn("SET text_lang = 'pt'", sql)
        self.assertIn("value.text_lang = 'pt_BR'", sql)
        self.assertIn("schema.short_id = 'dc'", sql)
        self.assertIn("field.element = 'description'", sql)
        self.assertIn("field.qualifier = 'abstract'", sql)
        self.assertNotIn("dc.language.iso", sql.split("UPDATE", 1)[1])

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

        self.assertIn("pt", stored_values)
        self.assertIn("en", stored_values)
        self.assertNotIn("pt_BR", stored_values)


if __name__ == "__main__":
    unittest.main()
