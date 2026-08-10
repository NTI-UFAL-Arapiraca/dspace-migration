import json
import tempfile
import unittest
from pathlib import Path

from dspace_migration.organization import (
    COMMUNITIES_FILE,
    MAPPING_FILE,
    _fetch_paginated_models,
    generate_import_script,
    get_saf_subpath,
    load_community_structure,
    load_curso_mapping,
)


class DummyModel:
    def __init__(self, resource):
        self.uuid = resource["uuid"]


class PaginatedClient:
    def __init__(self):
        self.calls = []

    def fetch_resource(self, url, params=None):
        self.calls.append((url, params))
        if url == "page-1":
            return {
                "_embedded": {"collections": [{"uuid": "1"}]},
                "_links": {"next": {"href": "page-2"}},
            }
        return {
            "_embedded": {"collections": [{"uuid": "2"}]},
            "_links": {},
        }


class OrganizationTests(unittest.TestCase):
    def test_repository_mapping_targets_exactly_the_configured_collections(self):
        tree = load_community_structure(COMMUNITIES_FILE)
        configured_paths = set()

        def visit(node, parent_path=()):
            node_path = (*parent_path, node["name"])
            for collection in node.get("collections", []):
                configured_paths.add(" > ".join((*node_path, collection["name"])))
            for child in node.get("subcommunities", []):
                visit(child, node_path)

        visit(tree)
        mapped_paths = {
            entry["new_path"] for entry in load_curso_mapping(MAPPING_FILE).values()
        }

        self.assertEqual(configured_paths, mapped_paths)

    def test_fetches_every_api_page(self):
        client = PaginatedClient()

        resources = _fetch_paginated_models(
            client, "page-1", "collections", DummyModel
        )

        self.assertEqual(["1", "2"], [resource.uuid for resource in resources])
        self.assertEqual(("page-1", {"size": 100}), client.calls[0])
        self.assertEqual(("page-2", None), client.calls[1])

    def test_rejects_duplicate_course_mappings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.json"
            path.write_text(json.dumps([
                {"old_name": "Curso", "new_path": "Raiz > A > Um"},
                {"old_name": "Curso", "new_path": "Raiz > A > Dois"},
            ]), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicado"):
                load_curso_mapping(path)

    def test_rejects_parent_traversal_in_saf_path(self):
        with self.assertRaisesRegex(ValueError, "inseguro"):
            get_saf_subpath("Raiz > .. > Coleção")

    def test_generates_quoted_import_commands_and_returns_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saf = root / "saf"
            (saf / "Polo A" / "Coleção B" / "item_1").mkdir(parents=True)
            uuids = root / "uuids.json"
            uuids.write_text(json.dumps({
                "Raiz > Polo A > Coleção B": "uuid-1",
            }), encoding="utf-8")
            output = root / "import.sh"

            count = generate_import_script(
                "admin@example.org",
                collection_uuids_file=uuids,
                saf_bundle_dir=saf,
                output_file=output,
            )

            script = output.read_text(encoding="utf-8")
            self.assertEqual(1, count)
            self.assertIn("-s '/dspace/saf_bundle/Polo A/Coleção B'", script)
            self.assertIn("-m '/dspace/saf_bundle/Polo A/Coleção B/mapfile.txt'", script)

    def test_missing_collection_mapping_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                generate_import_script(
                    collection_uuids_file=Path(tmp) / "missing.json",
                    saf_bundle_dir=tmp,
                    output_file=Path(tmp) / "import.sh",
                )


if __name__ == "__main__":
    unittest.main()
