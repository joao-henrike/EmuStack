import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate-manifests.py"
SPEC = importlib.util.spec_from_file_location("emustack_validate_manifests", MODULE_PATH)
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(VALIDATOR)


class ManifestValidationTests(unittest.TestCase):
    def test_repository_manifests_and_compose_are_consistent(self):
        errors = VALIDATOR.validate_repository(ROOT, include_compose=True)
        self.assertEqual(errors, [], "\n".join(errors))

    def test_duplicate_catalog_ids_fail_with_an_actionable_message(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            for filename in VALIDATOR.JSON_MANIFESTS:
                shutil.copy2(ROOT / filename, temp_root / filename)
            catalog_path = temp_root / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["emulators"][1]["id"] = catalog["emulators"][0]["id"]
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

            errors = VALIDATOR.validate_repository(temp_root, include_compose=False)

        self.assertTrue(any("ID duplicado" in error for error in errors), errors)

    def test_broken_catalog_environment_references_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            for filename in VALIDATOR.JSON_MANIFESTS:
                shutil.copy2(ROOT / filename, temp_root / filename)
            environments_path = temp_root / "environments.json"
            data = json.loads(environments_path.read_text(encoding="utf-8"))
            data["environments"] = data["environments"][:-1]
            environments_path.write_text(json.dumps(data), encoding="utf-8")

            errors = VALIDATOR.validate_repository(temp_root, include_compose=False)

        self.assertTrue(any("catalog/environment ID mismatch" in error for error in errors), errors)
 
    def test_save_paths_cover_catalog_ids_and_reject_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            for filename in VALIDATOR.JSON_MANIFESTS:
                shutil.copy2(ROOT / filename, temp_root / filename)
            paths_file = temp_root / "save-paths.json"
            data = json.loads(paths_file.read_text(encoding="utf-8"))
            duckstation = next(item for item in data["profiles"] if item["id"] == "duckstation")
            duckstation["home_paths"][0]["path"] = "../outside"
            paths_file.write_text(json.dumps(data), encoding="utf-8")

            errors = VALIDATOR.validate_repository(temp_root, include_compose=False)

        self.assertTrue(any("caminho inseguro" in error for error in errors), errors)

    def test_save_path_profile_set_must_match_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            for filename in VALIDATOR.JSON_MANIFESTS:
                shutil.copy2(ROOT / filename, temp_root / filename)
            paths_file = temp_root / "save-paths.json"
            data = json.loads(paths_file.read_text(encoding="utf-8"))
            data["profiles"] = data["profiles"][:-1]
            paths_file.write_text(json.dumps(data), encoding="utf-8")

            errors = VALIDATOR.validate_repository(temp_root, include_compose=False)

        self.assertTrue(any("save-path/catalog ID mismatch" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
