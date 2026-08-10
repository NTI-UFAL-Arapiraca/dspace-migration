import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dspace_migration.access import AccessPolicy, write_access_policies
from dspace_migration.pdfs import (
    ExtractionStats,
    cleanup_orphaned_contents,
    clear_managed_contents,
    decode_file_bytes,
    extract_pdfs,
    process_attachment,
    sanitize_filename,
)


class CleanupContentsTests(unittest.TestCase):
    def test_keeps_saf_options_when_the_referenced_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            item_dir = Path(tmp) / "item_1"
            item_dir.mkdir()
            (item_dir / "documento.pdf").write_bytes(b"%PDF-test")
            contents = item_dir / "contents"
            contents.write_text(
                "documento.pdf\tpermissions:-r 'Administrator'\n",
                encoding="utf-8",
            )

            cleanup_orphaned_contents(Path(tmp))

            self.assertEqual(
                "documento.pdf\tpermissions:-r 'Administrator'\n",
                contents.read_text(encoding="utf-8"),
            )

    def test_reextract_removes_only_files_listed_in_previous_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            item_dir = Path(tmp) / "item_1"
            item_dir.mkdir()
            managed = item_dir / "antigo.pdf"
            unrelated = item_dir / "nota-local.txt"
            managed.write_bytes(b"old")
            unrelated.write_text("preservar", encoding="utf-8")
            (item_dir / "contents").write_text(
                "antigo.pdf\tpermissions:-r 'Administrator'\n",
                encoding="utf-8",
            )

            clear_managed_contents(item_dir)

            self.assertFalse(managed.exists())
            self.assertFalse((item_dir / "contents").exists())
            self.assertTrue(unrelated.exists())


class AttachmentTests(unittest.TestCase):
    def test_decodes_postgresql_hex_and_base64_pdf(self):
        pdf = b"%PDF-test"

        self.assertEqual(pdf, decode_file_bytes(b"\\x" + pdf.hex().encode()))
        self.assertEqual(pdf, decode_file_bytes("JVBERi10ZXN0"))

    def test_sanitizes_unsafe_filename(self):
        self.assertEqual("pasta_arquivo_.pdf", sanitize_filename(" pasta/arquivo?.pdf "))

    def test_pdf_conversion_failure_preserves_original_and_reports_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = ExtractionStats()
            issues = []
            original = b"%PDF-original"
            with patch(
                "dspace_migration.pdfs.convert_to_pdfa",
                return_value=(original, False, "ghostscript indisponível"),
            ):
                saved = process_attachment(
                    publicacao_id=1,
                    anexo_id=2,
                    raw_name="documento.pdf",
                    arquivo=original,
                    item_dir=Path(tmp),
                    used_names=set(),
                    stats=stats,
                    issues=issues,
                )

            self.assertEqual("documento.pdf", saved)
            self.assertEqual(original, (Path(tmp) / saved).read_bytes())
            self.assertEqual(1, stats.pdfa_failures)
            self.assertEqual("PDFA_CONVERSION_FAILED", issues[0].issue_type)

    def test_full_extraction_writes_a_protected_saf_contents_entry(self):
        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, query, params):
                self.params = params

            def fetchall(self):
                return [(7, 11, "trabalho.pdf", b"%PDF-original")]

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()
                self.closed = False

            def cursor(self):
                return self.cursor_instance

            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saf = root / "saf"
            item = saf / "Polo" / "Coleção" / "item_7"
            item.mkdir(parents=True)
            write_access_policies(
                saf,
                {7: AccessPolicy("restricted", reason="não autorizado")},
            )
            connection = Connection()
            old_cwd = Path.cwd()
            os.chdir(root)
            try:
                with (
                    patch("dspace_migration.pdfs.SAF_BUNDLE_DIR", saf),
                    patch("dspace_migration.pdfs.connect", return_value=connection),
                    patch(
                        "dspace_migration.pdfs.convert_to_pdfa",
                        return_value=(b"%PDF-A", True, ""),
                    ),
                ):
                    extract_pdfs()
            finally:
                os.chdir(old_cwd)

            self.assertEqual(b"%PDF-A", (item / "trabalho.pdf").read_bytes())
            self.assertEqual(
                "trabalho.pdf\tpermissions:-r 'Administrator'\n",
                (item / "contents").read_text(encoding="utf-8"),
            )
            self.assertEqual([7], connection.cursor_instance.params["id_list"])
            self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
