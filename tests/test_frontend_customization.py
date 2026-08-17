import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCKER_ROOT = PROJECT_ROOT / "dspace-docker"


class FrontendCustomizationTests(unittest.TestCase):
    def test_compose_builds_custom_image_and_mounts_runtime_config(self):
        compose = (DOCKER_ROOT / "docker-compose-dist.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("dockerfile: Dockerfile.angular", compose)
        self.assertIn("DSPACE_APP_CONFIG_PATH: /app/config/local/config.prod.yml", compose)
        self.assertIn(
            "./frontend/config/config.prod.yml:/app/config/local/config.prod.yml:ro",
            compose,
        )

    def test_dockerfile_compiles_overlay_and_reuses_official_runtime(self):
        dockerfile = (DOCKER_ROOT / "Dockerfile.angular").read_text(
            encoding="utf-8"
        )

        self.assertIn("dspace-angular:${DSPACE_ANGULAR_TAG} AS build", dockerfile)
        self.assertIn("COPY frontend/themes/ /app/src/themes/", dockerfile)
        self.assertIn(
            "npm run merge-i18n -- -s src/themes/custom/assets/i18n", dockerfile
        )
        self.assertIn("npm run build:prod", dockerfile)
        self.assertLess(dockerfile.index("npm run merge-i18n"), dockerfile.index("npm run build:prod"))
        self.assertIn("dspace-angular:${DSPACE_ANGULAR_TAG}-dist AS runtime", dockerfile)
        self.assertIn("COPY --chown=node:node --from=build /app/dist /app/dist", dockerfile)

    def test_runtime_config_activates_custom_theme_first(self):
        config = (DOCKER_ROOT / "frontend/config/config.prod.yml").read_text(
            encoding="utf-8"
        )

        custom_position = config.index("- name: custom")
        fallback_position = config.index("- name: dspace")
        self.assertLess(custom_position, fallback_position)
        self.assertIn("fallbackLanguage: pt-BR", config)

    def test_anonymous_visitors_default_to_brazilian_portuguese(self):
        header = (
            DOCKER_ROOT / "frontend/themes/custom/app/header/header.component.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("DEFAULT_ANONYMOUS_LANGUAGE = 'pt-BR'", header)
        self.assertIn("getLanguageCodeFromCookie()", header)
        self.assertIn("isAuthenticationLoaded()", header)
        self.assertIn("if (!authenticated", header)
        self.assertIn(
            "setCurrentLanguageCode(DEFAULT_ANONYMOUS_LANGUAGE)", header
        )

    def test_custom_theme_suppresses_stock_home_news_banner(self):
        component = (
            DOCKER_ROOT
            / "frontend/themes/custom/app/home-page/home-news/home-news.component.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("export class HomeNewsComponent extends BaseComponent", component)
        self.assertIn("template: ''", component)
        self.assertNotIn("world leading open source repository", component)

    def test_untyped_item_shows_advisor_and_referees_after_authors(self):
        template = (
            DOCKER_ROOT
            / "frontend/themes/custom/app/item-page/simple/item-types/untyped-item"
            / "untyped-item.component.html"
        ).read_text(encoding="utf-8")

        authors = template.index("dc.contributor.author")
        advisor = template.index("dc.contributor.advisor")
        referees = template.index("dc.contributor.referee")
        following_field = template.index("journal.title")

        self.assertLess(authors, advisor)
        self.assertLess(advisor, referees)
        self.assertLess(referees, following_field)
        self.assertIn("'item.page.advisor'", template)
        self.assertIn("'item.page.referees'", template)

    def test_untyped_item_justifies_only_the_abstract_field(self):
        component_dir = (
            DOCKER_ROOT
            / "frontend/themes/custom/app/item-page/simple/item-types/untyped-item"
        )
        template = (component_dir / "untyped-item.component.html").read_text(
            encoding="utf-8"
        )
        component = (component_dir / "untyped-item.component.ts").read_text(
            encoding="utf-8"
        )
        styles = (component_dir / "untyped-item.component.scss").read_text(
            encoding="utf-8"
        )

        abstract_start = template.index("<ds-item-page-abstract-field")
        abstract_end = template.index("</ds-item-page-abstract-field>", abstract_start)
        abstract_markup = template[abstract_start:abstract_end]

        self.assertIn('class="document-abstract"', abstract_markup)
        self.assertIn("'./untyped-item.component.scss'", component)
        self.assertIn(".document-abstract", styles)
        self.assertIn("text-align: justify", styles)

    def test_untyped_item_localizes_issued_date_for_brazilian_portuguese(self):
        component_dir = (
            DOCKER_ROOT
            / "frontend/themes/custom/app/item-page/simple/item-types/untyped-item"
        )
        item_component = (component_dir / "untyped-item.component.ts").read_text(
            encoding="utf-8"
        )
        date_component = (
            component_dir / "date/localized-item-page-date-field.component.ts"
        ).read_text(encoding="utf-8")
        date_spec = (
            component_dir / "date/localized-item-page-date-field.component.spec.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("LocalizedItemPageDateFieldComponent", item_component)
        self.assertNotIn(
            "specific-field/date/item-page-date-field.component", item_component
        )
        self.assertIn("normalizedLanguage !== 'pt-br'", date_component)
        self.assertIn("`${day}/${month}/${year}`", date_component)
        self.assertIn("`${month}/${year}`", date_component)
        self.assertIn("'2026-02-30'", date_spec)

    def test_custom_component_registries_are_enabled(self):
        eager = (
            DOCKER_ROOT / "frontend/themes/eager-themes-components.ts"
        ).read_text(encoding="utf-8")
        listable = (
            DOCKER_ROOT / "frontend/themes/themes-listable-components.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("...CUSTOM_THEME_EAGER_COMPONENTS", eager)
        self.assertIn("...DSPACE_THEME_EAGER_COMPONENTS", eager)
        self.assertIn("...CUSTOM_LISTABLE_COMPONENTS", listable)
        self.assertIn("...DSPACE_LISTABLE_COMPONENTS", listable)

    def test_contributor_labels_are_translated(self):
        translations = {
            "en": ("Advisor", "Examination committee members"),
            "pt-BR": ("Orientador", "Membros avaliadores da banca"),
        }

        for language, labels in translations.items():
            with self.subTest(language=language):
                translation_file = (
                    DOCKER_ROOT
                    / "frontend/themes/custom/assets/i18n"
                    / f"{language}.json5"
                ).read_text(encoding="utf-8")
                for label in labels:
                    self.assertIn(label, translation_file)


if __name__ == "__main__":
    unittest.main()
