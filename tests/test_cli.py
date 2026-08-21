import io
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from dspace_migration.cli import migrate_all


class CliPipelineTests(unittest.TestCase):
    def test_skip_options_keep_step_numbers_consistent_and_apply_embargoes(self):
        output = io.StringIO()
        with (
            patch.object(
                sys,
                "argv",
                ["migrate", "--skip-docker", "--skip-stats", "--skip-oai"],
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

    def test_unified_pipeline_rebuilds_oai_after_existing_import(self):
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["migrate", "--skip-docker", "--skip-stats"]),
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

        run.assert_called_once_with(
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
        )
        self.assertIn("[6/6] Reconstruindo índice OAI-PMH", output.getvalue())


if __name__ == "__main__":
    unittest.main()
