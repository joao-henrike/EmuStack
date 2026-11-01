"""Phase 1 manager: no Docker daemon or network required for these tests."""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
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


    def test_nested_source_manifest_rejects_symlink_path(self):
        sandbox = self.root / "nested-fixture"
        sandbox.mkdir()
        (sandbox / ".gitmodules").write_text(
            '[submodule "thirdparty"]\n'
            '    path = externals/thirdparty\n'
            '    url = https://github.com/official/thing.git\n',
            encoding="utf-8"
        )
        (sandbox / "externals").symlink_to(self.root, target_is_directory=True)
        # Git should never receive a path that resolves through a symlink.
        with patch.object(manager.subprocess, "run") as run:
            run.return_value.stdout = "160000 " + "a" * 40 + " 0\texternals/thirdparty\n"
            with self.assertRaisesRegex(manager.ManagerError, "Submodule target escapes"):
                manager.submodule_entries(sandbox)

    def test_plan_deps_refuses_unsupported_profile_before_git(self):
        with self.assertRaisesRegex(manager.ManagerError, "No source build recipe"):
            manager.plan_deps("xbox-series")

    def test_staged_git_identity_is_source_commit_not_emustack_head(self):
        """Nested FFmpeg must resolve its own pinned SHA in a disposable copy."""
        parent = self.root / "upstream"
        child_source = self.root / "ffmpeg"
        stage = self.root / "staged-upstream"
        parent.mkdir()
        child_source.mkdir()

        def git(cwd, *args):
            completed = subprocess.run(
                ["git", "-C", str(cwd), *args], capture_output=True, text=True,
                check=True, timeout=30,
            )
            return completed.stdout.strip()

        for location in (parent, child_source):
            git(location, "init", "-q")
            git(location, "config", "user.name", "Unit Test")
            git(location, "config", "user.email", "test@invalid.example")

        (child_source / "artifact.txt").write_text("nested-dependency\n", encoding="utf-8")
        git(child_source, "add", "artifact.txt")
        git(child_source, "commit", "-qm", "pin ffmpeg source")
        nested_sha = git(child_source, "rev-parse", "HEAD")

        (parent / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
        git(parent, "-c", "protocol.file.allow=always", "submodule", "add",
            str(child_source), "externals/ffmpeg-core")
        manifest = parent / ".gitmodules"
        manifest.write_text(
            '[submodule "externals/ffmpeg-core"]\n'
            '    path = externals/ffmpeg-core\n'
            '    url = https://github.com/shadps4-emu/ext-ffmpeg-core.git\n',
            encoding="utf-8",
        )
        git(parent, "add", "-A")
        git(parent, "commit", "-qm", "pin parent and nested source")
        parent_sha = git(parent, "rev-parse", "HEAD")
        self.assertNotEqual(parent_sha, nested_sha)

        shutil.copytree(parent, stage, ignore=shutil.ignore_patterns(".git"))
        result = manager.stage_git_metadata(parent, stage)
        self.assertEqual(result["staged_git_repositories"], 2)
        self.assertEqual(git(stage, "rev-parse", "HEAD"), parent_sha)
        self.assertEqual(git(stage / "externals/ffmpeg-core", "rev-parse", "HEAD"),
                         nested_sha)
        self.assertEqual(git(parent, "rev-parse", "HEAD"), parent_sha)
        self.assertEqual(git(parent / "externals/ffmpeg-core", "rev-parse", "HEAD"),
                         nested_sha)
        self.assertEqual(git(stage, "status", "--porcelain"), "")

    def test_ppsspp_preflight_uses_sdl3_not_sdl2(self):
        recipe = manager.RECIPES["ppsspp"]
        self.assertEqual(recipe["pkg_config_required"], ["sdl3", "SDL3_ttf"])
        self.assertIn("libsdl3-dev", recipe["packages"])
        self.assertIn("libsdl3-ttf-dev", recipe["packages"])
        self.assertNotIn("libsdl2-dev", recipe["packages"])

    def test_shadps4_preflight_blocks_old_cmake_version(self):
        with patch.object(manager.shutil, "which", side_effect=lambda exe: "/usr/bin/" + exe), \
             patch.object(manager.subprocess, "run",
                          return_value=SimpleNamespace(returncode=0, stdout="cmake version 3.25.1\n")):
            report = manager.dependencies("shadps4")
        self.assertEqual(report["insufficient_versions"], [
            {"tool": "cmake", "required": "3.26", "found": "cmake version 3.25.1"}
        ])

    def test_kyty_launcher_preflight_blocks_old_qt6_version(self):
        with patch.object(manager.shutil, "which", side_effect=lambda exe: "/usr/bin/" + exe), \
             patch.object(manager.subprocess, "run",
                          return_value=SimpleNamespace(returncode=0, stdout="6.4.2\n")):
            report = manager.dependencies("kytyps5")
        self.assertEqual(report["insufficient_versions"], [
            {"tool": "Qt6Core", "required": "6.8", "found": "6.4.2"}
        ])

    def test_version_preflight_rejects_build_before_touching_source(self):
        with patch.object(manager.os, "geteuid", return_value=1000), \
             patch.object(manager, "dependencies", return_value={
                 "missing_commands": [], "missing_pkg_config": [],
                 "insufficient_versions": [{"tool": "cmake", "required": "3.26", "found": "3.25.1"}]
             }), patch.object(manager, "verify_source") as verify:
            with self.assertRaisesRegex(manager.ManagerError, r"cmake >= 3\.26"):
                manager.build("shadps4", 2, True)
        verify.assert_not_called()

    def test_isolated_builder_does_not_expose_docker_socket_or_privileged_mode(self):
        script = (MODULE_PATH.parents[0] / "phase1.sh").read_text()
        compatibility = (MODULE_PATH.parents[0] / "build-phase1-isolated.sh").read_text()
        dockerfile = (MODULE_PATH.parents[0] / "phase1-builder" / "Dockerfile").read_text()
        self.assertIn("phase1.sh", compatibility)
        self.assertIn("build", compatibility)
        self.assertIn("--read-only", script)
        self.assertIn("--cap-drop ALL", script)
        self.assertIn("no-new-privileges", script)
        self.assertIn("--yes-run-upstream-code", script)
        self.assertIn("dst=/workspace,readonly", script)
        self.assertIn("dst=/workspace/data,readonly", script)
        self.assertIn("dst=/workspace/data/emulator-manager", script)
        self.assertIn("dst=/workspace/data/environments/$profile_id/emulators", script)
        self.assertNotIn("/var/run/docker.sock", script)
        self.assertNotIn("--privileged", script)
        self.assertIn("debian:trixie-slim@sha256:", dockerfile)
        self.assertIn("libsdl3-dev", dockerfile)
        self.assertIn("qt6-base-dev", dockerfile)
        self.assertIn('case "$action" in status|deps|test|validate|build|build-all', script)
        self.assertIn("sync-deps", script)
        self.assertIn("install-file", script)
        self.assertIn("rollback", script)
        self.assertIn("history", script)
        self.assertIn("logs", script)
        for profile in ("kytyps5", "shadps4", "ppsspp", "melonds", "bsnes"):
            self.assertIn(profile, script)
        self.assertIn('--network "$network"', script)
        self.assertIn("network=none", script)
        self.assertIn("python3-yaml", dockerfile)
        self.assertIn("nodejs", dockerfile)
        self.assertIn("PYTHONPYCACHEPREFIX=/tmp/pycache", script)
        self.assertIn("data/imports", script)
        self.assertNotIn("apt-get install", script)
        self.assertNotIn("sudo ", script)

    def _make_runtime_bundle(self, name: str, content: str) -> Path:
        folder = self.root / ("package-" + content)
        folder.mkdir()
        entry = folder / name
        entry.write_bytes(b"\x7fELF" + content.encode("utf-8"))
        entry.chmod(0o755)
        (folder / "assets").mkdir()
        (folder / "assets" / "config.txt").write_text(content, encoding="utf-8")
        return folder

    def test_packaged_build_keeps_runtime_assets_and_launcher_under_one_console(self):
        source = self._make_runtime_bundle("PPSSPPSDL", "first")
        result = manager.install_build_bundle(
            "ppsspp", source, "PPSSPPSDL",
            {"source": "upstream-pinned", "commit": "a" * 40}
        )
        self.assertEqual(result["bundle_files"], 2)
        installed = self.root / result["bundle_directory"]
        self.assertEqual((installed / "assets/config.txt").read_text(), "first")
        launcher = self.root / result["installed"]
        self.assertIn("/custom-emulators/.emustack-bundles/", launcher.read_text())
        self.assertTrue(manager.status("ppsspp")[0]["bundle_hash_valid"])
        self.assertFalse((self.root / "data/environments/melonds/emulators/PPSSPPSDL").exists())

    def test_bundle_upgrade_and_rollback_use_original_matching_assets(self):
        first = manager.install_build_bundle(
            "ppsspp", self._make_runtime_bundle("PPSSPPSDL", "first"),
            "PPSSPPSDL", {"method": "pinned-source-build", "commit": "a" * 40}
        )
        second = manager.install_build_bundle(
            "ppsspp", self._make_runtime_bundle("PPSSPPSDL", "second"),
            "PPSSPPSDL", {"method": "pinned-source-build", "commit": "b" * 40}
        )
        self.assertNotEqual(first["bundle_sha256"], second["bundle_sha256"])
        versions = manager.history("ppsspp")
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["origin"]["bundle_sha256"], first["bundle_sha256"])
        manager.rollback("ppsspp")
        current = manager.status("ppsspp")[0]
        self.assertTrue(current["bundle_hash_valid"])
        self.assertEqual(current["managed_install"]["origin"]["bundle_sha256"],
                         first["bundle_sha256"])

    def test_bundle_rollback_rejects_corrupted_resources(self):
        first = manager.install_build_bundle(
            "ppsspp", self._make_runtime_bundle("PPSSPPSDL", "first"),
            "PPSSPPSDL", {"method": "pinned-source-build"}
        )
        manager.install_build_bundle(
            "ppsspp", self._make_runtime_bundle("PPSSPPSDL", "second"),
            "PPSSPPSDL", {"method": "pinned-source-build"}
        )
        (self.root / first["bundle_directory"] / "assets/config.txt").write_text("tampered")
        with self.assertRaisesRegex(manager.ManagerError, "bundle payload"):
            manager.rollback("ppsspp")
        self.assertTrue(manager.status("ppsspp")[0]["bundle_hash_valid"])

    def test_bundle_refuses_upstream_symlinks_without_mutation(self):
        folder = self._make_runtime_bundle("PPSSPPSDL", "outside")
        (folder / "assets" / "external").symlink_to(self.input)
        with self.assertRaisesRegex(manager.ManagerError, "symlink"):
            manager.install_build_bundle("ppsspp", folder, "PPSSPPSDL", {})
        self.assertFalse((self.root / "data/environments/ppsspp/emulators/PPSSPPSDL").exists())

    def test_bundle_idempotency_does_not_modify_immutable_payload(self):
        folder = self._make_runtime_bundle("PPSSPPSDL", "repeat")
        first = manager.install_build_bundle("ppsspp", folder, "PPSSPPSDL", {})
        second = manager.install_build_bundle("ppsspp", folder, "PPSSPPSDL", {})
        self.assertEqual(first["bundle_sha256"], second["bundle_sha256"])
        self.assertTrue(manager.status("ppsspp")[0]["bundle_hash_valid"])

    def test_bundle_executable_permissions_are_included_in_integrity(self):
        folder = self._make_runtime_bundle("PPSSPPSDL", "permissions")
        result = manager.install_build_bundle("ppsspp", folder, "PPSSPPSDL", {})
        self.assertTrue(manager.status("ppsspp")[0]["bundle_hash_valid"])
        entry = self.root / result["bundle_directory"] / "PPSSPPSDL"
        entry.chmod(0o644)
        self.assertFalse(manager.status("ppsspp")[0]["bundle_hash_valid"])

    def test_bundle_build_without_required_kyty_helper_is_rejected(self):
        work = self.root / "build"
        work.mkdir()
        (work / "package").mkdir()
        launcher = work / "package" / "kyty_launcher"
        launcher.write_bytes(b"fake")
        launcher.chmod(0o755)
        (work / "build").mkdir()
        with self.assertRaisesRegex(manager.ManagerError, "kyty_emulator runtime helper"):
            manager._build_package("kytyps5", work, self.root, launcher)

    def test_native_build_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(manager.ManagerError, "yes-run-upstream-code"):
            manager.build("ppsspp", 1, yes=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
