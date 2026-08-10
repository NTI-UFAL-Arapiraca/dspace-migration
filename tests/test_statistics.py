import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from dspace_migration.statistics import (
    _uniform_timestamps,
    generate_solr_docs,
    inject_statistics,
    read_mapfiles,
)


class MapfileTests(unittest.TestCase):
    def test_reads_valid_mapfiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Coleção" / "mapfile.txt"
            path.parent.mkdir()
            path.write_text("item_1 123456789/10\nitem_2 uuid-2\n", encoding="utf-8")

            self.assertEqual(
                {1: "123456789/10", 2: "uuid-2"},
                read_mapfiles(tmp),
            )

    def test_rejects_malformed_mapfile_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mapfile.txt"
            path.write_text("linha quebrada\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Linha inválida"):
                read_mapfiles(tmp)

    def test_rejects_conflicting_handles_for_same_source_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a").mkdir()
            (root / "b").mkdir()
            (root / "a" / "mapfile.txt").write_text(
                "item_1 123/1\n", encoding="utf-8"
            )
            (root / "b" / "mapfile.txt").write_text(
                "item_1 123/2\n", encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "conflitantes"):
                read_mapfiles(tmp)


class StatisticsDocumentTests(unittest.TestCase):
    NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)

    def test_uniform_timestamps_handles_zero_one_and_multiple(self):
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)

        self.assertEqual([], _uniform_timestamps(0, start, self.NOW))
        self.assertEqual(1, len(_uniform_timestamps(1, start, self.NOW)))
        timestamps = _uniform_timestamps(3, start, self.NOW)
        self.assertEqual("2020-01-01T00:00:00Z", timestamps[0])
        self.assertEqual("2026-08-10T12:00:00Z", timestamps[-1])

    def test_generated_documents_are_idempotent(self):
        first = generate_solr_docs("item-uuid", 3, 2020, now=self.NOW)
        second = generate_solr_docs("item-uuid", 3, 2020, now=self.NOW)

        self.assertEqual([doc["uid"] for doc in first], [doc["uid"] for doc in second])
        self.assertEqual(3, len(set(doc["uid"] for doc in first)))

    def test_invalid_year_uses_five_year_fallback(self):
        docs = generate_solr_docs("item-uuid", 2, "inválido", now=self.NOW)

        self.assertEqual("2021-08-11T12:00:00Z", docs[0]["time"])
        self.assertEqual("2026-08-10T12:00:00Z", docs[-1]["time"])

    def test_injection_never_sends_more_than_configured_batch(self):
        sent_sizes = []
        with (
            patch("dspace_migration.statistics.read_mapfiles", return_value={1: "h/1"}),
            patch(
                "dspace_migration.statistics.resolve_uuids_from_dspace",
                return_value={"h/1": "uuid-1"},
            ),
            patch(
                "dspace_migration.statistics.fetch_view_counts",
                return_value={1: {"visualizacoes": 5, "ano_pub": 2020}},
            ),
            patch("dspace_migration.statistics.SOLR_BATCH_SIZE", 2),
            patch(
                "dspace_migration.statistics._post_to_solr",
                side_effect=lambda docs, _: sent_sizes.append(len(docs)),
            ),
            patch("dspace_migration.statistics._commit_solr"),
        ):
            inject_statistics(saf_bundle_dir="saf", solr_url="solr")

        self.assertEqual([2, 2, 1], sent_sizes)


if __name__ == "__main__":
    unittest.main()
