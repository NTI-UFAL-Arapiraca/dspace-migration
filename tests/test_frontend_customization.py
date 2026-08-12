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
        self.assertIn("COPY frontend/themes/custom/ /app/src/themes/custom/", dockerfile)
        self.assertIn("RUN npm run build:prod", dockerfile)
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


if __name__ == "__main__":
    unittest.main()
