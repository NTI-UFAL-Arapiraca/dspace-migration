import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts/register_custom_fields.sh"
REGISTRY = PROJECT_ROOT / "config/registries/migration-metadata.xml"


class MetadataRegistryTests(unittest.TestCase):
    def test_registry_defines_only_used_local_fields_without_changing_schema(self):
        root = ET.parse(REGISTRY).getroot()
        self.assertEqual("dspace-dc-types", root.tag)
        self.assertIsNone(root.find("dc-schema"))
        fields = [
            ".".join(field.findtext(part) for part in ("schema", "element", "qualifier"))
            for field in root.findall("dc-type")
        ]
        self.assertEqual(len(fields), len(set(fields)))
        self.assertEqual({
            "local.course.name", "local.campus.name", "local.identifier.legacy",
            "dc.contributor.coadvisor", "dc.contributor.referee",
            "dc.description.note",
        }, set(fields))
        sql = (PROJECT_ROOT / "sql/extract_metadata.sql").read_text()
        for field in set(fields) - {"local.identifier.legacy"}:
            self.assertIn(f'AS "{field}"', sql)
        for field in root.findall("dc-type"):
            self.assertTrue(field.findtext("scope_note", "").strip())

    def run_script(self, failure_stage="", failure_status="0"):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            docker = directory / "docker"
            docker.write_text('''#!/usr/bin/env bash
set -eu
printf '%s\\n' "$*" >> "$DOCKER_CALL_LOG"
if [[ $1 == cp && $FAILURE_STAGE == cp ]]; then
    exit "$FAILURE_STATUS"
fi
if [[ $1 == exec && $3 == mktemp ]]; then
    printf '%s\\n' /tmp/test-registry.xml
elif [[ $1 == exec && $3 == /dspace/bin/dspace ]]; then
    if [[ $FAILURE_STAGE == importer ]]; then
        exit "$FAILURE_STATUS"
    fi
fi
''')
            docker.chmod(0o755)
            log = directory / "calls"
            result = subprocess.run(
                ["bash", str(SCRIPT), "production-backend"],
                cwd=directory,
                env={
                    **os.environ,
                    "PATH": f"{directory}:{os.environ['PATH']}",
                    "DOCKER_CALL_LOG": str(log),
                    "FAILURE_STAGE": failure_stage,
                    "FAILURE_STATUS": failure_status,
                },
                capture_output=True,
                text=True,
            )
            return result, log.read_text().splitlines()

    def test_runs_official_loader_from_another_directory_and_cleans_temp_file(self):
        result, calls = self.run_script()
        self.assertEqual(0, result.returncode, result.stderr)
        copy_source = calls[1].split()[1]
        self.assertEqual(REGISTRY, Path(copy_source).resolve())
        self.assertIn("production-backend:/tmp/test-registry.xml", calls[1])
        self.assertEqual(
            "exec production-backend /dspace/bin/dspace registry-loader -m /tmp/test-registry.xml",
            calls[2],
        )
        self.assertEqual(
            "exec production-backend rm -f -- /tmp/test-registry.xml", calls[-1]
        )

    def test_copy_or_import_failure_propagates_and_cleans_temp_file(self):
        for stage in ("cp", "importer"):
            with self.subTest(stage=stage):
                result, calls = self.run_script(stage, "7")
                self.assertEqual(7, result.returncode)
                self.assertNotIn("Registro concluído", result.stdout)
                self.assertEqual(
                    "exec production-backend rm -f -- /tmp/test-registry.xml",
                    calls[-1],
                )
                if stage == "cp":
                    self.assertFalse(any("registry-loader" in call for call in calls))


if __name__ == "__main__":
    unittest.main()
