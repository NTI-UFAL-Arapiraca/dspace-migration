import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from dspace_migration.access import (
    ACCESS_POLICIES_FILENAME,
    AccessPolicy,
    build_contents_entry,
    contents_entry_filename,
    determine_access_policy,
    read_access_policies,
    write_access_policies,
)


class AccessPolicyTests(unittest.TestCase):
    TODAY = date(2026, 8, 10)

    def test_future_date_creates_temporary_embargo(self):
        policy = determine_access_policy("2027-03-15", today=self.TODAY)

        self.assertEqual("embargo", policy.access_type)
        self.assertEqual(date(2027, 3, 15), policy.start_date)

    def test_expired_date_is_open(self):
        policy = determine_access_policy(
            "2025-01-01",
            today=self.TODAY,
        )

        self.assertIsNone(policy)

    def test_invalid_populated_date_fails_closed(self):
        policy = determine_access_policy("sem data", today=self.TODAY)

        self.assertEqual("restricted", policy.access_type)
        self.assertIsNone(policy.start_date)

    def test_not_authorized_without_date_is_permanently_restricted(self):
        policy = determine_access_policy(None, False, today=self.TODAY)

        self.assertEqual("restricted", policy.access_type)

    def test_restriction_observation_does_not_change_access_policy(self):
        policy = determine_access_policy(
            None,
            True,
            provenance="Acesso restrito solicitado pela autora",
            today=self.TODAY,
        )

        self.assertIsNone(policy)

    def test_positive_authorization_note_does_not_create_restriction(self):
        policy = determine_access_policy(
            None,
            True,
            note="Publicação autorizada pela autora",
            today=self.TODAY,
        )

        self.assertIsNone(policy)

    def test_contents_entry_restricts_and_filename_parser_preserves_it(self):
        policy = AccessPolicy("embargo", date(2027, 1, 1))

        line = build_contents_entry("trabalho final.pdf", policy)

        self.assertEqual(
            "trabalho final.pdf\tpermissions:-r 'Administrator'",
            line,
        )
        self.assertEqual("trabalho final.pdf", contents_entry_filename(line))

    def test_manifest_round_trip_is_outside_item_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            policies = {
                10: AccessPolicy("embargo", date(2027, 1, 1), "teste"),
                11: None,
                12: AccessPolicy("restricted", reason="sem autorização"),
            }

            write_access_policies(bundle, policies)
            loaded = read_access_policies(bundle)

            self.assertTrue((bundle / ACCESS_POLICIES_FILENAME).is_file())
            self.assertEqual({10, 12}, set(loaded))
            self.assertEqual(date(2027, 1, 1), loaded[10].start_date)
            serialized = json.loads(
                (bundle / ACCESS_POLICIES_FILENAME).read_text(encoding="utf-8")
            )
            self.assertNotIn("11", serialized)


if __name__ == "__main__":
    unittest.main()
