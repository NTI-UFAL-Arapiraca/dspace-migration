import io
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import call, patch

from dspace_migration.cli import migrate_all


class CliPipelineTests(unittest.TestCase):
    def test_people_run_after_embargoes_before_statistics_and_indexes(self):
        order = []
        result = SimpleNamespace(created=2, reused=1, items_updated=3)
        with (
            patch.object(sys, "argv", ["migrate", "--skip-docker"]),
            patch("dspace_migration.cli.process_data"),
            patch("dspace_migration.cli.extract_pdfs"),
            patch("dspace_migration.cli.setup_dspace", return_value={"c": "uuid"}),
            patch("dspace_migration.cli.generate_import_script"),
            patch("dspace_migration.cli.apply_embargoes", side_effect=lambda: (
                order.append("embargoes") or SimpleNamespace(items=1, bitstreams=1)
            )),
            patch("dspace_migration.cli.apply_people", side_effect=lambda: order.append("people") or result),
            patch("dspace_migration.cli.inject_statistics", side_effect=lambda: order.append("statistics")),
            patch("dspace_migration.cli.rebuild_oai_index", side_effect=lambda _: order.append("oai")),
            patch("dspace_migration.cli.generate_sitemaps", side_effect=lambda _: order.append("sitemaps")),
            patch("dspace_migration.cli.check_and_report_issues"),
            redirect_stdout(io.StringIO()),
        ):
            migrate_all()
        self.assertEqual(["embargoes", "people", "statistics", "oai", "sitemaps"], order)

    def test_skip_options_keep_step_numbers_consistent_and_apply_embargoes(self):
        output = io.StringIO()
        with (
            patch.object(
                sys,
                "argv",
                [
                    "migrate",
                    "--skip-docker",
                    "--skip-stats",
                    "--skip-oai",
                    "--skip-sitemaps",
                    "--skip-people",
                ],
            ),
            patch("dspace_migration.cli.process_data"),
            patch("dspace_migration.cli.extract_pdfs"),
            patch("dspace_migration.cli.setup_dspace", return_value={"c": "uuid"}),
            patch("dspace_migration.cli.generate_import_script"),
            patch(
                "dspace_migration.cli.apply_embargoes",
                return_value=SimpleNamespace(items=1, bitstreams=1),
            ) as apply,
            patch("dspace_migration.cli.check_and_report_issues"),
            redirect_stdout(output),
        ):
            migrate_all()

        apply.assert_called_once_with()
        rendered = output.getvalue()
        self.assertIn("[1/5]", rendered)
        self.assertIn("[5/5] Aplicando políticas de embargo", rendered)
        self.assertNotIn("[6/5]", rendered)

    def test_unified_pipeline_rebuilds_oai_and_generates_sitemaps(self):
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["migrate", "--skip-docker", "--skip-stats", "--skip-people"]),
            patch("dspace_migration.cli.process_data"),
            patch("dspace_migration.cli.extract_pdfs"),
            patch("dspace_migration.cli.setup_dspace", return_value={"c": "uuid"}),
            patch("dspace_migration.cli.generate_import_script"),
            patch(
                "dspace_migration.cli.apply_embargoes",
                return_value=SimpleNamespace(items=1, bitstreams=1),
            ),
            patch("dspace_migration.cli.subprocess.run") as run,
            patch("dspace_migration.cli.check_and_report_issues"),
            redirect_stdout(output),
        ):
            migrate_all()

        self.assertEqual(
            [
                call(
                    [
                        "docker",
                        "exec",
                        "dspace",
                        "/dspace/bin/dspace",
                        "oai",
                        "import",
                        "-c",
                    ],
                    check=True,
                ),
                call(
                    [
                        "docker",
                        "exec",
                        "dspace",
                        "/dspace/bin/dspace",
                        "generate-sitemaps",
                    ],
                    check=True,
                ),
            ],
            run.call_args_list,
        )
        rendered = output.getvalue()
        self.assertIn("[6/7] Reconstruindo índice OAI-PMH", rendered)
        self.assertIn("[7/7] Gerando sitemaps XML e HTML", rendered)


if __name__ == "__main__":
    unittest.main()
