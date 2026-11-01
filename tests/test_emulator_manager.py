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

    def test_traversal_through_managed_path_is_rejected(self):
        crafted = self.root / "data" / ".." / ".." / "outside"
        with self.assertRaisesRegex(manager.ManagerError, "unsafe traversal"):
            manager.check_managed_path(crafted)

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


    def test_unmanaged_existing_binary_is_not_silently_replaced(self):
        dest = self.root / "data/environments/ppsspp/emulators/PPSSPPSDL"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"unmanaged user file")
        with self.assertRaisesRegex(manager.ManagerError, "unmanaged"):
            manager.install_artifact("ppsspp", self.input, "PPSSPPSDL",
                                     {"method": "test"}, self.digest)
        self.assertEqual(dest.read_bytes(), b"unmanaged user file")

    def test_metadata_write_failure_restores_the_previous_binary(self):
        manager.install_artifact("ppsspp", self.input, "PPSSPPSDL",
                                 {"method": "test"}, self.digest)
        dest = self.root / "data/environments/ppsspp/emulators/PPSSPPSDL"
        new = self.root / "new.bin"
        new.write_bytes(b"second fake binary")
        checksum = hashlib.sha256(new.read_bytes()).hexdigest()
        with patch.object(manager, "write_record", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                manager.install_artifact("ppsspp", new, "PPSSPPSDL",
                                         {"method": "test"}, checksum)
        self.assertEqual(dest.read_bytes(), self.input.read_bytes())
        self.assertEqual(manager.active("ppsspp")["sha256"], self.digest)

    def test_update_to_different_binary_name_requires_uninstall(self):
        manager.install_artifact("ppsspp", self.input, "PPSSPPSDL",
                                 {"method": "test"}, self.digest)
        with self.assertRaisesRegex(manager.ManagerError, "uninstall"):
            manager.install_artifact("ppsspp", self.input, "PPSSPPQt",
                                     {"method": "test"}, self.digest)

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

    def test_only_five_source_builds_have_recipes(self):
        self.assertEqual(set(manager.RECIPES), {"kytyps5", "shadps4", "ppsspp", "melonds", "bsnes"})
        for identifier in manager.RECIPES:
            item = manager.dependencies(identifier)
            self.assertEqual(item["source_build"], "configured")
            self.assertEqual(len(item["source_commit"]), 40)
        with self.assertRaisesRegex(manager.ManagerError, "No reviewed"):
            manager.build("rpcs3", 2, yes=True)

    def test_binary_static_format_identification_never_runs_the_file(self):
        elf = self.root / "static.elf"
        contents = bytearray(64)
        contents[:4] = b"\x7fELF"
        contents[4] = 2
        contents[5] = 1
        contents[18:20] = (62).to_bytes(2, "little")
        elf.write_bytes(bytes(contents))
        self.assertEqual(manager.inspect_binary(elf)["architecture_hint"], "x86_64")
        self.input.write_bytes(b"MZ" + b"0" * 64)
        self.assertEqual(manager.inspect_binary(self.input)["format"], "possible-PE-Windows")

    def test_bsnes_dependency_probes_detect_missing_pkgconfig_headers(self):
        original = manager.RECIPES["bsnes"]
        self.assertIn("gtk+-3.0", original["pkg_config_required"])
        self.assertIn("sdl2", original["pkg_config_required"])
        def command(name):
            return "/usr/bin/" + name
        with patch.object(manager.shutil, "which", side_effect=command), \
             patch.object(manager.subprocess, "run") as probe:
            probe.return_value.returncode = 1
            report = manager.dependencies("bsnes")
        self.assertEqual(report["missing_commands"], [])
        self.assertEqual(report["missing_pkg_config"], ["gtk+-3.0", "sdl2"])
        self.assertEqual(probe.call_count, 2)

    def test_bsnes_build_refuses_missing_pkgconfig_before_compilation(self):
        with patch.object(manager.os, "geteuid", return_value=1000), \
             patch.object(manager, "dependencies", return_value={
                 "missing_commands": [], "missing_pkg_config": ["gtk+-3.0"]
             }), patch.object(manager, "verify_source") as verify:
            with self.assertRaisesRegex(manager.ManagerError, "pkg-config modules: gtk"):
                manager.build("bsnes", 2, True)
        verify.assert_not_called()

    def test_build_command_failure_exposes_bounded_tail_and_log_path(self):
        work = self.root / "data" / "emulator-manager"
        work.mkdir(parents=True)
        log = work / "failed.log"
        with patch.object(manager.subprocess, "run") as run:
            run.return_value.returncode = 2
            with self.assertRaises(manager.ManagerError) as failed:
                manager.run_build(["make", "-C", "bsnes"], work, log)
        self.assertIn("failed.log", str(failed.exception))
        self.assertIn("last log lines", str(failed.exception))
        self.assertIn("Build command failed (2)", str(failed.exception))


    def test_melonds_pkg_config_preflight_includes_qt6_components(self):
        modules = manager.RECIPES["melonds"]["pkg_config_required"]
        for module in ("Qt6Core", "Qt6Widgets", "Qt6Multimedia", "Qt6Svg"):
            self.assertIn(module, modules)
        with patch.object(manager.shutil, "which", side_effect=lambda name: "/usr/bin/" + name), \
             patch.object(manager.subprocess, "run") as mock_run:
            mock_run.return_value.returncode = 1
            report = manager.dependencies("melonds")
        self.assertIn("Qt6Core", report["missing_pkg_config"])

    def test_nested_sync_requires_explicit_operator_consent(self):
        with self.assertRaisesRegex(manager.ManagerError, "yes-download-submodules"):
            manager.sync_deps("ppsspp", jobs=2, allow_download=False)

    def test_nested_sync_rejects_root_and_unsupported_recipes(self):
        with self.assertRaisesRegex(manager.ManagerError, "No reviewed"):
            manager.sync_deps("xbox-one", jobs=2, allow_download=True)
        with patch.object(manager.os, "geteuid", return_value=0):
            with self.assertRaisesRegex(manager.ManagerError, "as root"):
                manager.sync_deps("ppsspp", jobs=2, allow_download=True)

    def test_nested_source_manifest_rejects_untrusted_urls_before_download(self):
        sandbox = self.root / "nested-fixture"
        sandbox.mkdir()
        manifest = sandbox / ".gitmodules"
        manifest.write_text(
            '[submodule "thirdparty"]\n'
            '    path = externals/thirdparty\n'
            '    url = file:///tmp/evil.git\n',
            encoding="utf-8"
        )
        with self.assertRaisesRegex(manager.ManagerError, "Unreviewed submodule origin"):
            manager.submodule_entries(sandbox)

    def test_nested_source_manifest_rejects_path_traversal(self):
        sandbox = self.root / "nested-fixture"
        sandbox.mkdir()
        (sandbox / ".gitmodules").write_text(
            '[submodule "thirdparty"]\n'
            '    path = ../outside\n'
            '    url = https://github.com/safe/example.git\n',
            encoding="utf-8"
        )
        with self.assertRaisesRegex(manager.ManagerError, "Unsafe submodule path"):
            manager.submodule_entries(sandbox)

    def test_native_build_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(manager.ManagerError, "yes-run-upstream-code"):
            manager.build("ppsspp", 1, yes=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
