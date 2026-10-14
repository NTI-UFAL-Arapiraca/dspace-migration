import copy
import fcntl
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dspace_migration.people import (
    PERSON_FIELDS, SOURCE_FIELD, apply_people, build_manifest, write_json,
)


COLLECTION = "00000000-0000-4000-8000-000000000001"
PUBLICATION = "00000000-0000-4000-8000-000000000002"
PERSON = "00000000-0000-4000-8000-000000000003"


def source_row(item_id=42):
    rows = {field: [] for field in PERSON_FIELDS}
    rows["dc.contributor.author"] = [{
        "source": "ud_biblioteca_publicacao_autor", "id": 7,
        "given_name": "Ana", "family_name": "Silva",
    }]
    rows["dc.contributor.advisor"] = [{
        "source": "ud_biblioteca_publicacao_orientador", "id": 7,
        "given_name": "Ana", "family_name": "Silva",
    }]
    rows["dc.contributor.referee"] = copy.deepcopy(rows["dc.contributor.advisor"])
    return {"id_origem": item_id, "pessoas": rows}


class FakeClient:
    def __init__(self):
        self.mode = "false"
        self.writes = []
        self.items = {PUBLICATION: {
            "uuid": PUBLICATION,
            "metadata": {
                "dc.contributor.author": [{"value": "Silva, Ana", "language": None, "securityLevel": 1}],
                "dc.contributor.advisor": [{"value": "Silva, Ana", "language": None}],
                "dc.contributor.referee": [{"value": "Silva, Ana", "language": None}],
                "dc.description.degree": [{"value": "Curso", "language": "pt"}],
                "dc.publisher.department": [{"value": "Campus", "language": None}],
                "dc.description.abstract": [
                    {"value": "Resumo", "language": "pt"},
                    {"value": "Abstract", "language": "en"},
                ],
                "dc.description.provenance": [{"value": "Nota administrativa"}],
            },
        }}

    def authenticate(self):
        return True

    def response(self, data, status=200):
        return SimpleNamespace(status_code=status, json=lambda: copy.deepcopy(data))

    def api_get(self, url, params=None):
        if "/config/properties/" in url:
            return self.response({"values": [self.mode]})
        if "/core/collections/" in url:
            return self.response({"metadata": {"dspace.entity.type": [{"value": "Person"}]}})
        if url.endswith("/core/items"):
            return self.response({"_embedded": {"items": list(self.items.values())}, "page": {"totalPages": 1}})
        return self.response(self.items[url.rsplit("/", 1)[-1]])

    def resolve_identifier_to_dso(self, handle):
        return SimpleNamespace(uuid=PUBLICATION)

    def api_post(self, url, params, json):
        assert url.endswith("/core/items")
        assert params == {"owningCollection": COLLECTION}
        person_uuid = f"00000000-0000-4000-8000-{len(self.items)+10:012d}"
        self.items[person_uuid] = {"uuid": person_uuid, **copy.deepcopy(json)}
        self.writes.append(("create", person_uuid))
        return self.response(self.items[person_uuid], 201)

    def api_patch(self, url, operation, path, value, params=None):
        assert params == {"projection": "allLanguages"}
        item = self.items[url.rsplit("/", 1)[-1]]
        field = path.removeprefix("/metadata/")
        self.writes.append((operation, field))
        if operation == "remove":
            del item["metadata"][field]
        else:
            item["metadata"][field] = copy.deepcopy(value)
        return self.response(item)


class ManifestTests(unittest.TestCase):
    def test_source_identity_reuses_advisor_for_board_but_keeps_author_separate(self):
        rows = [source_row(), source_row(43)]
        manifest = build_manifest(rows)
        self.assertEqual(2, len(manifest["people"]))
        self.assertEqual(
            manifest["items"]["42"]["dc.contributor.advisor"],
            manifest["items"]["43"]["dc.contributor.referee"],
        )
        self.assertNotEqual(
            manifest["items"]["42"]["dc.contributor.author"],
            manifest["items"]["42"]["dc.contributor.advisor"],
        )
        self.assertEqual("Silva, Ana", rows[0]["dc.contributor.advisor"])

    def test_conflicting_names_for_same_source_fail(self):
        rows = [source_row(), source_row(43)]
        rows[1]["pessoas"]["dc.contributor.author"][0]["given_name"] = "Outra"
        with self.assertRaisesRegex(ValueError, "conflitante"):
            build_manifest(rows)

    def test_missing_identity_or_duplicate_participation_fails(self):
        with self.assertRaisesRegex(ValueError, "consulta deve fornecer"):
            build_manifest([{"id_origem": 42, "dc.contributor.author": "Silva, Ana"}])
        row = source_row()
        row["pessoas"]["dc.contributor.author"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicada"):
            build_manifest([row])


class PeopleApplicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        write_json(self.root / "people.json", build_manifest([source_row()]))
        (self.root / "mapfile.txt").write_text("item_42 123456789/42\n")
        self.client = FakeClient()
        self.mock_client = patch("dspace_migration.people.DSpaceClient", return_value=self.client)
        self.mock_client.start()
        self.addCleanup(self.mock_client.stop)
        self.env = patch.dict(os.environ, {"DSPACE_API_URL": "http://example.test/server/api"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_application(self, **kwargs):
        return apply_people(self.root, COLLECTION, **kwargs)

    def test_links_roles_preserves_translations_and_is_idempotent(self):
        before = copy.deepcopy(self.client.items[PUBLICATION]["metadata"])
        first = self.run_application()
        self.assertEqual(2, first.created)
        metadata = self.client.items[PUBLICATION]["metadata"]
        author = metadata["dc.contributor.author"][0]["authority"]
        advisor = metadata["dc.contributor.advisor"][0]["authority"]
        self.assertNotEqual(author, advisor)
        self.assertEqual(advisor, metadata["dc.contributor.referee"][0]["authority"])
        self.assertEqual(600, metadata["dc.contributor.author"][0]["confidence"])
        self.assertEqual(1, metadata["dc.contributor.author"][0]["securityLevel"])
        self.assertEqual(before["dc.description.abstract"], metadata["dc.description.abstract"])
        self.assertEqual(before["dc.description.provenance"], metadata["dc.description.provenance"])
        self.assertEqual("Curso", metadata["local.course.name"][0]["value"])
        self.assertEqual("pt", metadata["local.course.name"][0]["language"])
        self.assertNotIn("dc.description.degree", metadata)
        self.assertNotIn("dc.publisher.department", metadata)
        writes = len(self.client.writes)
        second = self.run_application()
        self.assertEqual(0, second.created)
        self.assertEqual(2, second.reused)
        self.assertEqual(1, second.items_unchanged)
        self.assertEqual(writes, len(self.client.writes))

    def test_recovers_person_created_before_checkpoint_was_written(self):
        key = "odoo:ud_biblioteca_publicacao_autor:7"
        self.client.items[PERSON] = {"uuid": PERSON, "metadata": {
            "dspace.entity.type": [{"value": "Person"}], SOURCE_FIELD: [{"value": key}],
        }}
        result = self.run_application()
        self.assertEqual(1, result.created)
        self.assertEqual(1, result.reused)
        self.assertEqual(PERSON, self.client.items[PUBLICATION]["metadata"]["dc.contributor.author"][0]["authority"])

    def test_dry_run_does_not_create_accounts_people_links_or_checkpoint(self):
        result = self.run_application(dry_run=True)
        self.assertEqual(2, result.created)
        self.assertEqual([], self.client.writes)
        self.assertFalse((self.root / "people-map.json").exists())

    def test_incompatible_model_and_missing_handles_fail_before_mutation(self):
        self.client.mode = "true"
        with self.assertRaisesRegex(RuntimeError, "Authority Framework"):
            self.run_application()
        self.client.mode = "false"
        (self.root / "mapfile.txt").write_text("")
        with self.assertRaisesRegex(ValueError, "sem handle"):
            self.run_application()
        self.assertEqual([], self.client.writes)

    def test_name_conflict_or_existing_authority_is_not_overwritten(self):
        metadata = self.client.items[PUBLICATION]["metadata"]
        metadata["dc.contributor.author"][0]["authority"] = PERSON
        with self.assertRaisesRegex(ValueError, "Autoridade conflitante"):
            self.run_application()
        metadata["dc.contributor.author"][0].pop("authority")
        metadata["dc.contributor.author"][0]["value"] = "Outra pessoa"
        with self.assertRaisesRegex(ValueError, "divergem"):
            self.run_application()
        self.assertEqual([], self.client.writes)

    def test_conflicting_academic_fields_are_not_overwritten(self):
        self.client.items[PUBLICATION]["metadata"]["local.course.name"] = [{"value": "Outro curso"}]
        with self.assertRaisesRegex(ValueError, "Valores conflitantes"):
            self.run_application()
        self.assertEqual([], self.client.writes)

    def test_duplicate_source_people_fail_instead_of_selecting_one(self):
        metadata = {"dspace.entity.type": [{"value": "Person"}], SOURCE_FIELD: [{"value": "odoo:ud_biblioteca_publicacao_autor:7"}]}
        self.client.items[PERSON] = {"uuid": PERSON, "metadata": metadata}
        other = "00000000-0000-4000-8000-000000000004"
        self.client.items[other] = {"uuid": other, "metadata": metadata}
        with self.assertRaisesRegex(ValueError, "Mais de uma Person"):
            self.run_application()
        self.assertEqual([], self.client.writes)

    def test_interrupted_rename_keeps_old_values_and_resumes_without_duplicates(self):
        original_patch = self.client.api_patch

        def fail_remove(**kwargs):
            if kwargs["operation"] == "remove":
                raise RuntimeError("interrupção")
            return original_patch(**kwargs)

        with patch.object(self.client, "api_patch", side_effect=fail_remove):
            with self.assertRaisesRegex(RuntimeError, "interrupção"):
                self.run_application()
        metadata = self.client.items[PUBLICATION]["metadata"]
        self.assertIn("local.course.name", metadata)
        self.assertIn("dc.description.degree", metadata)
        result = self.run_application()
        self.assertEqual(0, result.created)
        self.assertEqual(2, result.reused)
        self.assertNotIn("dc.description.degree", metadata)

    def test_parallel_writer_on_same_bundle_is_rejected(self):
        with (self.root / "people.lock").open("a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "Outra migração"):
                self.run_application()
        self.assertEqual([], self.client.writes)

    def test_checkpoint_from_another_target_is_rejected(self):
        write_json(self.root / "people-map.json", {
            "api_url": "http://other.test/server/api", "collection_uuid": COLLECTION, "people": {},
        })
        with self.assertRaisesRegex(ValueError, "outro destino"):
            self.run_application()
        self.assertEqual([], self.client.writes)


if __name__ == "__main__":
    unittest.main()
