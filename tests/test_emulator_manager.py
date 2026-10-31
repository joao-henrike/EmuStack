"""Phase 1 manager: no Docker daemon or network required for these tests."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "emulator-manager.py"
SPEC = importlib.util.spec_from_file_location("emustack_emulator_manager", MODULE_PATH)
manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manager)


class EmulatorManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original_catalog = manager.CATALOG
        self.original_lock = manager.SOURCE_LOCK
        self.patches = [
            patch.object(manager, "ROOT", self.root),
            patch.object(manager, "STATE", self.root / "data" / "emulator-manager"),
        ]
        for item in self.patches:
            item.start()
        self.input = self.root / "fixture.AppImage"
        self.input.write_bytes(b"fake test emulator binary")
        self.digest = hashlib.sha256(self.input.read_bytes()).hexdigest()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_imported_binary_is_per_environment_and_hash_validated(self):
        record = manager.install_artifact(
            "ppsspp", self.input, "PPSSPPSDL", {"method": "test"}, self.digest)
        expected = self.root / "data/environments/ppsspp/emulators/PPSSPPSDL"
        self.assertEqual(expected.read_bytes(), self.input.read_bytes())
        self.assertEqual(record["sha256"], self.digest)
        self.assertFalse(record["runtime_tested"])
        self.assertTrue(manager.status("ppsspp")[0]["managed_hash_valid"])
        self.assertFalse((self.root / "data/environments/melonds/emulators/PPSSPPSDL").exists())

    def test_sha_mismatch_rejects_without_touching_install(self):
        with self.assertRaisesRegex(manager.ManagerError, "SHA-256 mismatch"):
            manager.install_artifact(
                "ppsspp", self.input, "PPSSPPSDL", {"method": "test"}, "0" * 64)
        self.assertFalse((self.root / "data/environments/ppsspp/emulators").exists())

    def test_bad_binary_name_and_unsupported_console_rejected(self):
        with self.assertRaisesRegex(manager.ManagerError, "not allowlisted"):
            manager.install_artifact("ppsspp", self.input, "../../wrong",
                                     {"method": "test"}, self.digest)
        with self.assertRaisesRegex(manager.ManagerError, "no supported"):
            manager.install_artifact("xbox-one", self.input, "dummy",
                                     {"method": "test"}, self.digest)

    def test_symlink_output_is_not_overwritten(self):
        dest = self.root / "data/environments/ppsspp/emulators/PPSSPPSDL"
        dest.parent.mkdir(parents=True, exist_ok=True)
        victim = self.root / "victim"
        victim.write_bytes(b"keep me")
        dest.symlink_to(victim)
        with self.assertRaisesRegex(manager.ManagerError, "symlink"):
            manager.install_artifact("ppsspp", self.input, "PPSSPPSDL",
                                     {"method": "test"}, self.digest)
        self.assertEqual(victim.read_bytes(), b"keep me")

    def test_symlink_parent_cannot_redirect_install(self):
        parent = self.root / "data/environments/ppsspp"
        parent.mkdir(parents=True)
        outside = self.root / "outside"
        outside.mkdir()
        (parent / "emulators").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(manager.ManagerError, "symlink"):
            manager.install_artifact("ppsspp", self.input, "PPSSPPSDL",
                                     {"method": "test"}, self.digest)
        self.assertEqual(list(outside.iterdir()), [])

    def test_update_rollback_and_uninstall_preserve_previous_binary(self):
        manager.install_artifact("ppsspp", self.input, "PPSSPPSDL",
                                 {"method": "test"}, self.digest)
        new = self.root / "another.bin"
        new.write_bytes(b"second fake emulator")
        other_sha = hashlib.sha256(new.read_bytes()).hexdigest()
        manager.install_artifact("ppsspp", new, "PPSSPPSDL",
                                 {"method": "test"}, other_sha)
        self.assertEqual(len(manager.history("ppsspp")), 1)
        rollback = manager.rollback("ppsspp")
        self.assertEqual(rollback["sha256"], self.digest)
        self.assertEqual((self.root / "data/environments/ppsspp/emulators/PPSSPPSDL").read_bytes(),
                         self.input.read_bytes())
        self.assertEqual(len(manager.history("ppsspp")), 2)
        removed = manager.uninstall("ppsspp")
        self.assertEqual(removed["removed"], "ppsspp")
        self.assertFalse((self.root / "data/environments/ppsspp/emulators/PPSSPPSDL").exists())
        self.assertIsNone(manager.active("ppsspp"))
        self.assertEqual(len(manager.history("ppsspp")), 3)

    def test_rollback_after_uninstall_restores_last_managed_binary(self):
        manager.install_artifact("melonds", self.input, "melonDS",
                                 {"method": "test"}, self.digest)
        manager.uninstall("melonds")
        self.assertIsNone(manager.active("melonds"))
        restored = manager.rollback("melonds")
        self.assertEqual(restored["sha256"], self.digest)
        self.assertTrue(manager.status("melonds")[0]["managed_hash_valid"])


    def test_modified_managed_binary_is_not_deleted(self):
        manager.install_artifact("ppsspp", self.input, "PPSSPPSDL",
                                 {"method": "test"}, self.digest)
        dest = self.root / "data/environments/ppsspp/emulators/PPSSPPSDL"
        dest.write_bytes(b"modified")
        with self.assertRaisesRegex(manager.ManagerError, "modified"):
            manager.uninstall("ppsspp")
        self.assertTrue(dest.exists())

    def test_status_covers_all_catalog_profiles(self):
        statuses = manager.status()
        self.assertEqual(len(statuses), 20)
        self.assertEqual(len({s["id"] for s in statuses}), 20)
        xbox = next(s for s in statuses if s["id"] == "xbox-series")
        self.assertFalse(xbox["source_build"])
        self.assertEqual(xbox["runtime"], "unsupported")

    def test_only_four_source_builds_have_recipes(self):
        self.assertEqual(set(manager.RECIPES), {"shadps4", "ppsspp", "melonds", "bsnes"})
        for identifier in manager.RECIPES:
            item = manager.dependencies(identifier)
            self.assertEqual(item["source_build"], "configured")
            self.assertEqual(len(item["source_commit"]), 40)
        with self.assertRaisesRegex(manager.ManagerError, "No reviewed"):
            manager.build("kytyps5", 2, yes=True)

    def test_native_build_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(manager.ManagerError, "yes-run-upstream-code"):
            manager.build("ppsspp", 1, yes=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
