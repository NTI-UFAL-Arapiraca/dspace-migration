import copy
import fcntl
import json
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from dspace_migration.people import (
    PERSON_FIELDS, SOURCE_FIELD, apply_people, build_manifest, write_json,
    normalize_email, normalize_lattes, read_manifest, _refresh_profiles,
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
        parts = path.removeprefix("/metadata/").split("/")
        field = parts[0]
        index = parts[1] if len(parts) > 1 else None
        self.writes.append((operation, path))
        values = item["metadata"].get(field, [])
        # DSpace 10.1 consumes only the first array element, even at field level.
        parsed = copy.deepcopy(value[0] if isinstance(value, list) else value)
        if operation == "remove":
            if index is None:
                del item["metadata"][field]
            else:
                del values[int(index)]
        elif operation == "add":
            values.insert(len(values) if index == "-" else 0, parsed)
            item["metadata"][field] = values
        else:
            assert operation == "replace"
            if index is None:
                item["metadata"][field] = [parsed]
            else:
                values[int(index)] = parsed
        return self.response(item)


class ManifestTests(unittest.TestCase):
    def test_extracts_profile_without_changing_names_or_participations(self):
        row = source_row()
        row["pessoas"]["dc.contributor.author"][0]["email"] = " ana@EXAMPLE.ORG "
        profile = {"email": "ana@example.org", "lattes": "http://lattes.cnpq.br/1234567890123456/", "degree": "Dr.ª"}
        for field in ("dc.contributor.advisor", "dc.contributor.referee"):
            row["pessoas"][field][0].update(profile)
        manifest = build_manifest([row])
        author = manifest["people"]["odoo:ud_biblioteca_publicacao_autor:7"]
        advisor = manifest["people"]["odoo:ud_biblioteca_publicacao_orientador:7"]
        self.assertEqual("ana@example.org", author["email"])
        self.assertEqual("https://lattes.cnpq.br/1234567890123456", advisor["lattes"])
        self.assertEqual("Dr.ª", advisor["degree"])
        self.assertEqual("Silva, Ana", row["dc.contributor.author"])

    def test_invalid_contacts_are_reported_without_exposing_values(self):
        row = source_row()
        row["pessoas"]["dc.contributor.author"][0].update(email="invalid-contact", lattes="javascript:alert(1)")
        manifest = build_manifest([row])
        self.assertEqual(2, len(manifest["profile_issues"]))
        self.assertNotIn("invalid-contact", json.dumps(manifest))
        self.assertNotIn("javascript:", json.dumps(manifest))
        self.assertIsNone(normalize_email("name@example.org; other@example.org"))
        self.assertIsNone(normalize_email("name@example.org:8080"))
        self.assertIsNone(normalize_lattes("https://lattes.cnpq.br.evil.test/1234567890123456"))
        self.assertIsNone(normalize_lattes("https://user@lattes.cnpq.br/1234567890123456"))
        self.assertEqual("https://lattes.cnpq.br/1234567890123456", normalize_lattes("1234567890123456"))
        self.assertEqual("https://lattes.cnpq.br/1234567890123456", normalize_lattes("lattes.cnpq.br/1234567890123456"))
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

    def add_profile(self):
        manifest = read_manifest(self.root)
        manifest["people"]["odoo:ud_biblioteca_publicacao_orientador:7"].update({
            "email": "ana@example.org", "degree": "Dr.ª", "lattes": "https://lattes.cnpq.br/1234567890123456",
        })
        write_json(self.root / "people.json", manifest)

    def test_creates_profiles_and_enriches_existing_people_without_duplicate_fields(self):
        self.run_application()
        self.add_profile()
        before = copy.deepcopy(self.client.items[PUBLICATION])
        result = self.run_application()
        self.assertEqual(0, result.created)
        self.assertEqual(1, result.people_updated)
        self.assertEqual(before, self.client.items[PUBLICATION])
        person = next(x for x in self.client.items.values() if x["metadata"].get("person.email"))
        self.assertEqual("Dr.ª", person["metadata"]["local.person.degree"][0]["value"])
        writes = len(self.client.writes)
        self.assertEqual(0, self.run_application().people_updated)
        self.assertEqual(writes, len(self.client.writes))

    def test_new_person_receives_full_profile_on_creation(self):
        self.add_profile()
        result = self.run_application()
        self.assertEqual(2, result.created)
        people = [x for x in self.client.items.values() if x["metadata"].get("person.email")]
        self.assertEqual(1, len(people))
        self.assertEqual("https://lattes.cnpq.br/1234567890123456", people[0]["metadata"]["person.identifier.lattes"][0]["value"])

    def test_profile_conflict_fails_before_mutating_any_person_or_work(self):
        self.run_application()
        self.add_profile()
        # Author and advisor share their name; identity stays table + ID.
        for item in self.client.items.values():
            if any(v["value"] == "odoo:ud_biblioteca_publicacao_orientador:7" for v in item["metadata"].get(SOURCE_FIELD, [])):
                item["metadata"]["person.email"] = [{"value": "curated@example.org"}]
        writes = len(self.client.writes)
        with self.assertRaisesRegex(ValueError, "Perfil existente diverge"):
            self.run_application()
        self.assertEqual(writes, len(self.client.writes))

    def test_refresh_dry_run_does_not_write_manifest_or_profiles(self):
        self.run_application()
        self.add_profile()
        refreshed = read_manifest(self.root)
        old_manifest = (self.root / "people.json").read_bytes()
        writes = len(self.client.writes)
        with patch("dspace_migration.people._refresh_profiles", return_value=refreshed):
            self.assertEqual(1, self.run_application(refresh_profiles=True, dry_run=True).people_updated)
        self.assertEqual(old_manifest, (self.root / "people.json").read_bytes())
        self.assertEqual(writes, len(self.client.writes))

    def test_refresh_source_is_readonly_and_rejects_changed_participations(self):
        connection = unittest.mock.MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [source_row()]
        with patch("dspace_migration.people.psycopg2.connect", return_value=connection) as connect:
            refreshed = _refresh_profiles(self.root)
            self.assertEqual(read_manifest(self.root), refreshed)
            self.assertEqual("-c default_transaction_read_only=on", connect.call_args.kwargs["options"])
            self.assertEqual(([42],), cursor.execute.call_args.args[1])
            cursor.fetchall.return_value = [source_row(43)]
            with self.assertRaisesRegex(ValueError, "Participações mudaram"):
                _refresh_profiles(self.root)

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

    def test_updates_both_referees_in_existing_order_without_duplicates(self):
        row = source_row()
        second = {"source": "ud_biblioteca_publicacao_orientador", "id": 8,
                  "given_name": "Bruno", "family_name": "Costa"}
        row["pessoas"]["dc.contributor.referee"].append(second)
        write_json(self.root / "people.json", build_manifest([row]))
        metadata = self.client.items[PUBLICATION]["metadata"]
        metadata["dc.contributor.referee"].insert(0, {
            "value": "Costa, Bruno", "language": "pt", "securityLevel": 1,
        })
        before = copy.deepcopy(metadata["dc.contributor.referee"])
        self.run_application()
        values = metadata["dc.contributor.referee"]
        self.assertEqual([v["value"] for v in before], [v["value"] for v in values])
        self.assertEqual(2, len({v["authority"] for v in values}))
        self.assertTrue(all(v["confidence"] == 600 for v in values))
        self.assertEqual("pt", values[0]["language"])
        self.assertEqual(1, values[0]["securityLevel"])
        self.assertIn(("replace", "/metadata/dc.contributor.referee/1"), self.client.writes)
        writes = len(self.client.writes)
        self.assertEqual(1, self.run_application().items_unchanged)
        self.assertEqual(writes, len(self.client.writes))

    def test_resumes_after_first_participation_was_saved(self):
        original = self.client.api_patch

        def fail_author(**kwargs):
            if kwargs["path"] == "/metadata/dc.contributor.author/0":
                raise RuntimeError("interrupção")
            return original(**kwargs)

        with patch.object(self.client, "api_patch", side_effect=fail_author):
            with self.assertRaisesRegex(RuntimeError, "interrupção"):
                self.run_application()
        self.assertEqual(2, self.run_application().reused)
        self.assertEqual(1, self.run_application().items_unchanged)

    def test_dry_run_does_not_create_accounts_people_links_or_checkpoint(self):
        result = self.run_application(dry_run=True)
        self.assertEqual(2, result.created)
        self.assertEqual([], self.client.writes)
        self.assertFalse((self.root / "people-map.json").exists())
        self.assertFalse((self.root / "people.lock").exists())

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

    def test_resumes_multivalue_rename_after_only_first_value_was_copied(self):
        metadata = self.client.items[PUBLICATION]["metadata"]
        metadata["dc.description.degree"].append({
            "value": "Course", "language": "en", "authority": PERSON,
            "confidence": 600, "securityLevel": 1,
        })
        before = copy.deepcopy(metadata["dc.description.degree"])
        original = self.client.api_patch

        def fail_second_copy(**kwargs):
            if kwargs["path"] == "/metadata/local.course.name/-":
                raise RuntimeError("interrupção")
            return original(**kwargs)

        with patch.object(self.client, "api_patch", side_effect=fail_second_copy):
            with self.assertRaisesRegex(RuntimeError, "interrupção"):
                self.run_application()
        self.assertEqual(before, metadata["dc.description.degree"])
        self.assertEqual(1, len(metadata["local.course.name"]))
        self.assertEqual(2, self.run_application().reused)
        self.assertNotIn("dc.description.degree", metadata)
        self.assertEqual(2, len(metadata["local.course.name"]))
        for old, new in zip(before, metadata["local.course.name"]):
            for key, value in old.items():
                self.assertEqual(value, new[key])
        self.assertEqual(1, self.run_application().items_unchanged)

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
