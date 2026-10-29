import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit-save-layout.py"
SPEC = importlib.util.spec_from_file_location("emustack_save_layout_audit", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(AUDIT)


class SaveLayoutAuditTests(unittest.TestCase):
    def test_audit_covers_every_environment_and_does_not_create_missing_storage(self):
        with tempfile.TemporaryDirectory() as temp:
            data_root = Path(temp) / "environments"
            report = AUDIT.audit_save_layout(ROOT, data_root)

            environment_manifest = json.loads((ROOT / "environments.json").read_text(encoding="utf-8"))
            self.assertEqual(
                {item["profile_id"] for item in report["profiles"]},
                {item["id"] for item in environment_manifest["environments"]},
            )
            self.assertEqual(report["mode"], "read-only")
            self.assertFalse(data_root.exists())
            self.assertEqual(report["summary"]["profiles_with_unsafe_paths"], 0)
            self.assertTrue(all(p["home_directory"]["state"] == "missing" for p in report["profiles"]))
            self.assertTrue(all(p["separate_saves_directory"]["state"] == "missing" for p in report["profiles"]))

    def test_documented_duckstation_user_directory_is_observed_without_exposing_names(self):
        with tempfile.TemporaryDirectory() as temp:
            data_root = Path(temp) / "environments"
            home = data_root / "duckstation" / "home"
            candidate = home / ".local" / "share" / "duckstation"
            candidate.mkdir(parents=True)
            (candidate / "card.mcd").write_bytes(b"sample-memory-card")
            (data_root / "duckstation" / "saves").mkdir(parents=True)

            report = AUDIT.audit_save_layout(ROOT, data_root)
            profile = next(item for item in report["profiles"] if item["profile_id"] == "duckstation")
            observed = next(item for item in profile["candidate_paths"] if item["path_relative_to_home"] == ".local/share/duckstation")

            self.assertEqual(profile["status"], "candidate-directory-observed-not-proof-of-save-use")
            self.assertEqual(observed["state"], "observed-directory")
            self.assertEqual(observed["file_count"], 1)
            self.assertEqual(observed["total_bytes"], len(b"sample-memory-card"))
            serialized = json.dumps(report)
            self.assertNotIn("card.mcd", serialized)
            self.assertNotIn(str(data_root), serialized)

    def test_symlinked_candidate_is_reported_without_following_it(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            data_root = temp_root / "environments"
            home = data_root / "duckstation" / "home"
            (home / ".local" / "share").mkdir(parents=True)
            external = temp_root / "outside"
            external.mkdir()
            (external / "secret-save.bin").write_bytes(b"private")
            (home / ".local" / "share" / "duckstation").symlink_to(external, target_is_directory=True)

            report = AUDIT.audit_save_layout(ROOT, data_root)
            profile = next(item for item in report["profiles"] if item["profile_id"] == "duckstation")
            observed = next(item for item in profile["candidate_paths"] if item["path_relative_to_home"] == ".local/share/duckstation")

            self.assertEqual(observed["state"], "unsafe-symlink")
            self.assertEqual(observed["file_count"], 0)
            self.assertEqual(profile["status"], "unsafe-path-needs-review")
            self.assertNotIn("secret-save.bin", json.dumps(report))

    def test_audit_rejects_manifest_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            (temp_root / "save-paths.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "profiles": [{
                        "id": "duckstation",
                        "storage_model": "home-relative",
                        "confidence": "documented-upstream",
                        "home_paths": [{"path": "../escape", "kind": "user-data", "purpose": "invalid"}],
                    }],
                }),
                encoding="utf-8",
            )
            (temp_root / "environments.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "environments": [{
                        "id": "duckstation",
                        "directories": {
                            "root": "data/environments/duckstation",
                            "config_home": "data/environments/duckstation/home",
                            "saves": "data/environments/duckstation/saves",
                        },
                    }],
                }),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "inside the environment data root"):
                AUDIT.audit_save_layout(temp_root, temp_root / "data" / "environments")


if __name__ == "__main__":
    unittest.main(verbosity=2)
