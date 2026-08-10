import unittest
import json
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dspace_migration.access import AccessPolicy
from dspace_migration.embargoes import (
    MIGRATION_POLICY_NAME,
    apply_embargoes,
    _ensure_embargo_policy,
    _original_bitstreams,
)


class FakeClient:
    class PatchOperation:
        ADD = "add"
        REPLACE = "replace"

    def __init__(self, existing=None):
        self.existing = existing or []
        self.created = None
        self.patched = None

    def get_resource_policies_iter(self, parent, action):
        self.search = (parent, action)
        return iter(self.existing)

    def create_resource_policy(self, policy, parent, group):
        self.created = (policy, parent, group)
        return policy

    def api_patch(self, **kwargs):
        self.patched = kwargs
        return SimpleNamespace(status_code=200, text="")


class EmbargoResourcePolicyTests(unittest.TestCase):
    def test_creates_anonymous_read_policy_starting_at_release_date(self):
        client = FakeClient()
        policy = AccessPolicy("embargo", date(2027, 4, 5), "motivo")

        outcome = _ensure_embargo_policy(client, "bitstream-1", "anonymous-1", policy)

        self.assertEqual("created", outcome)
        created, parent, group = client.created
        self.assertEqual("bitstream-1", parent)
        self.assertEqual("anonymous-1", group)
        self.assertEqual("READ", created.action)
        self.assertEqual("2027-04-05", created.startDate)

    def test_does_not_duplicate_an_unchanged_migration_policy(self):
        existing = SimpleNamespace(
            name=MIGRATION_POLICY_NAME,
            startDate="2027-04-05",
            links={"self": {"href": "policy-url"}},
        )
        client = FakeClient([existing])
        policy = AccessPolicy("embargo", date(2027, 4, 5))

        outcome = _ensure_embargo_policy(client, "bitstream-1", "anonymous-1", policy)

        self.assertEqual("unchanged", outcome)
        self.assertIsNone(client.created)
        self.assertIsNone(client.patched)

    def test_replaces_release_date_on_an_existing_migration_policy(self):
        existing = SimpleNamespace(
            name=MIGRATION_POLICY_NAME,
            startDate="2027-04-05",
            links={"self": {"href": "policy-url"}},
        )
        client = FakeClient([existing])
        policy = AccessPolicy("embargo", date(2028, 6, 7))

        outcome = _ensure_embargo_policy(
            client, "bitstream-1", "anonymous-1", policy
        )

        self.assertEqual("updated", outcome)
        self.assertEqual("replace", client.patched["operation"])
        self.assertEqual("/startDate", client.patched["path"])
        self.assertEqual("2028-06-07", client.patched["value"])

    def test_collects_original_bitstreams_using_paginated_iterators(self):
        class Client:
            def get_bundles_iter(self, parent):
                return iter([
                    SimpleNamespace(name="ORIGINAL", uuid="bundle-1"),
                    SimpleNamespace(name="THUMBNAIL", uuid="bundle-2"),
                ])

            def get_bitstreams_iter(self, bundle):
                return iter([SimpleNamespace(uuid=f"bitstream-{bundle.uuid}")])

        item = SimpleNamespace(
            as_dict=lambda: {
                "uuid": "item-1",
                "type": "item",
                "metadata": {},
                "_links": {},
            },
            links={},
        )

        bitstreams = _original_bitstreams(Client(), item)

        self.assertEqual(["bitstream-bundle-1"], [b.uuid for b in bitstreams])

    def test_full_application_reads_manifest_mapfile_and_creates_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "access_policies.json").write_text(json.dumps({
                "7": {
                    "type": "embargo",
                    "startDate": "2099-01-01",
                    "reason": "teste",
                }
            }), encoding="utf-8")
            collection = root / "Coleção"
            collection.mkdir()
            (collection / "mapfile.txt").write_text(
                "item_7 123456789/7\n", encoding="utf-8"
            )

            client = SimpleNamespace()
            client.authenticate = lambda: True
            client.search_groups_by_metadata_iter = lambda _: iter([
                SimpleNamespace(name="Anonymous", uuid="anonymous-uuid")
            ])
            client.resolve_identifier_to_dso = lambda _: SimpleNamespace(
                uuid="item-uuid", links={}
            )
            client.get_bundles_iter = lambda parent: iter([
                SimpleNamespace(name="ORIGINAL", uuid="bundle-uuid", links={})
            ])
            client.get_bitstreams_iter = lambda bundle: iter([
                SimpleNamespace(uuid="bitstream-uuid")
            ])
            client.get_resource_policies_iter = lambda parent, action: iter([])
            created = []
            client.create_resource_policy = (
                lambda policy, parent, group: created.append((policy, parent, group))
                or policy
            )

            with patch(
                "dspace_migration.embargoes.DSpaceClient", return_value=client
            ):
                result = apply_embargoes(saf_bundle_dir=root)

            self.assertEqual(1, result.items)
            self.assertEqual(1, result.bitstreams)
            self.assertEqual(1, result.created)
            self.assertEqual("bitstream-uuid", created[0][1])
            self.assertEqual("anonymous-uuid", created[0][2])

    def test_metadata_only_embargo_does_not_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "access_policies.json").write_text(json.dumps({
                "8": {
                    "type": "embargo",
                    "startDate": "2099-01-01",
                    "reason": "teste",
                }
            }), encoding="utf-8")
            (root / "mapfile.txt").write_text(
                "item_8 123456789/8\n", encoding="utf-8"
            )
            client = SimpleNamespace(
                authenticate=lambda: True,
                search_groups_by_metadata_iter=lambda _: iter([
                    SimpleNamespace(name="Anonymous", uuid="anonymous-uuid")
                ]),
                resolve_identifier_to_dso=lambda _: SimpleNamespace(
                    uuid="item-uuid", links={}
                ),
                get_bundles_iter=lambda parent: iter([]),
            )

            with patch(
                "dspace_migration.embargoes.DSpaceClient", return_value=client
            ):
                result = apply_embargoes(saf_bundle_dir=root)

            self.assertEqual(1, result.without_bitstreams)
            self.assertEqual(0, result.bitstreams)


if __name__ == "__main__":
    unittest.main()
