import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
import tarfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
INSTALLER = PROJECT / "scripts" / "install-upstream.py"


class InstallerTests(unittest.TestCase):
    def test_debian_dependency_filter_rejects_packages_without_an_install_candidate(self):
        script = (PROJECT / "scripts" / "install-available-apt.sh").read_text(encoding="utf-8")
        self.assertIn('apt-cache policy "$1"', script)
        self.assertIn('[ "$candidate" != "(none)" ]', script)
        self.assertNotIn('apt-cache show "$package"', script)

    def test_skip_network_writes_a_complete_20_entry_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report_path = root / "report.json"
            target = root / "installed"
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "--skip-network", "--target", str(target),
                 "--catalog", str(PROJECT / "catalog.json"), "--report", str(report_path)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            data = json.loads(report_path.read_text(encoding="utf-8"))
            catalog = json.loads((PROJECT / "catalog.json").read_text(encoding="utf-8"))
            expected = {item["id"] for item in catalog["emulators"]}
            self.assertEqual(set(data["items"]), expected)
            self.assertEqual(len(data["items"]), 20)
            self.assertEqual(data["schema_version"], 2)
            self.assertEqual(data["items"]["xbox-one"]["status"], "unsupported-no-runner")
            self.assertEqual(data["items"]["xbox-series"]["status"], "unsupported-no-runner")
            for profile_id, item in data["items"].items():
                self.assertEqual(item["profile_id"], profile_id)
                self.assertEqual(item["installation_status"], item["status"])
                self.assertIn("host_architecture", item["evidence"])
                self.assertEqual(item["evidence"]["installer_architecture"], item["evidence"]["host_architecture"])
                self.assertIn("physical host/GPU is not attested", item["evidence"]["architecture_basis"])
                self.assertIn(item["execution_test"]["status"], {"not-run", "passed", "failed"})
                self.assertIn(item["runtime_test"]["status"], {"not-run", "passed", "failed"})
                self.assertIsInstance(item["execution_test"]["reason"], str)
                self.assertIsInstance(item["runtime_test"]["reason"], str)

    def test_downloader_rejects_non_allowlisted_host_before_network_access(self):
        spec = importlib.util.spec_from_file_location("install_upstream", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "asset.bin"
            with unittest.mock.patch.object(module.urllib.request, "urlopen", side_effect=AssertionError("network should not be called")) as urlopen_mock:
                with self.assertRaises(ValueError):
                    module.download_to_path("https://malicious.example/payload", destination)
            urlopen_mock.assert_not_called()
            self.assertFalse(destination.exists())

    def test_official_sources_are_allowlisted(self):
        spec = importlib.util.spec_from_file_location("install_upstream", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        expected = {"duckstation", "vita3k", "shadps4", "rpcs3", "pcsx2", "xenia-canary",
                    "xemu", "cemu", "azahar", "melonds", "mgba", "mesen"}
        self.assertTrue(expected.issubset(module.GITHUB_SOURCES))
        for _, config in module.GITHUB_SOURCES.items():
            self.assertTrue(config["repos"])
            self.assertTrue(all("/" in repo and not repo.startswith("http") for repo in config["repos"]))


    def test_pinned_release_resolves_exact_tag_and_asset(self):
        spec = importlib.util.spec_from_file_location("install_upstream", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        release = {"tag_name": "v1.2.3", "assets": [{
            "name": "rpcs3.AppImage", "browser_download_url": "https://github.com/RPCS3/rpcs3-binaries-linux/releases/download/v1.2.3/rpcs3.AppImage", "size": 10,
        }]}
        source_spec = {"pattern": r"(?i).*\.AppImage$", "kind": "appimage", "repos": ["RPCS3/rpcs3-binaries-linux"]}
        pin = {"mode": "pinned", "tag": "v1.2.3", "asset": "rpcs3.AppImage", "repo": "RPCS3/rpcs3-binaries-linux", "sha256": "a" * 64}
        with unittest.mock.patch.object(module, "github_release_by_tag", return_value=release) as get_release:
            picked = module.pick_asset("RPCS3/rpcs3-binaries-linux", source_spec, pin)
        get_release.assert_called_once_with("RPCS3/rpcs3-binaries-linux", "v1.2.3")
        self.assertEqual(picked[1]["name"], "rpcs3.AppImage")
        module.verify_locked_sha256("a" * 64, pin)
        with self.assertRaises(ValueError):
            module.verify_locked_sha256("c" * 64, pin)

    def test_strict_lock_skips_unpinned_release_without_network(self):
        spec = importlib.util.spec_from_file_location("install_upstream", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            catalog_by_id = {"rpcs3": {"id": "rpcs3", "binary_names": ["rpcs3.AppImage"]}}
            report = {}
            with unittest.mock.patch.object(module, "github_releases", side_effect=AssertionError("network must not be called")):
                module.install_github_asset("rpcs3", module.GITHUB_SOURCES["rpcs3"], target,
                                            catalog_by_id, report, lock_item={"mode": "skip-upstream"}, strict_lock=True)
            self.assertEqual(report["rpcs3"]["status"], "skipped-by-lock")

    def test_tar_symlink_entry_cannot_escape_install_directory(self):
        spec = importlib.util.spec_from_file_location("install_upstream", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / "links.tar"
            with tarfile.open(archive, "w") as tf:
                link = tarfile.TarInfo("outside-link")
                link.type = tarfile.SYMTYPE
                link.linkname = "../../escape"
                tf.addfile(link)
            destination = root / "out"
            module.safe_extract(archive, destination)
            self.assertFalse((destination / "outside-link").exists())
            self.assertFalse((root.parent / "escape").exists())

    def test_zip_path_traversal_is_rejected(self):
        spec = importlib.util.spec_from_file_location("install_upstream", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("../escape.txt", "not allowed")
            with self.assertRaises(ValueError):
                module.safe_extract(archive, root / "out")
            self.assertFalse((root / "escape.txt").exists())


    def test_archive_payload_promotes_atomically_and_updates_relative_alias(self):
        spec = importlib.util.spec_from_file_location("install_upstream_atomic", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = root / "rpcs3-payload"
            project.mkdir()
            (project / "old-runner").write_text("old", encoding="utf-8")
            alias = root / "rpcs3"
            alias.symlink_to("rpcs3-payload/old-runner")
            stage = Path(tempfile.mkdtemp(prefix=".rpcs3-stage-", dir=root))
            selected = stage / "new-runner"
            selected.write_text("new", encoding="utf-8")
            selected.chmod(0o755)

            module._atomic_promote_payload(stage, project, selected, alias)

            self.assertEqual((project / "new-runner").read_text(encoding="utf-8"), "new")
            self.assertFalse((project / "old-runner").exists())
            self.assertTrue(alias.is_symlink())
            self.assertEqual(alias.read_text(encoding="utf-8"), "new")
            self.assertEqual(os.readlink(alias), "rpcs3-payload/new-runner")
            self.assertFalse(stage.exists())
            self.assertFalse(list(root.glob(".*.backup-*")))
            self.assertFalse(list(root.glob(".*.new-*")))

    def test_archive_payload_rolls_back_when_alias_promotion_fails(self):
        spec = importlib.util.spec_from_file_location("install_upstream_atomic_rollback", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = root / "rpcs3-payload"
            project.mkdir()
            (project / "old-runner").write_text("old-payload", encoding="utf-8")
            alias = root / "rpcs3"
            alias.symlink_to("rpcs3-payload/old-runner")
            stage = Path(tempfile.mkdtemp(prefix=".rpcs3-stage-", dir=root))
            selected = stage / "new-runner"
            selected.write_text("new-payload", encoding="utf-8")

            original_replace = Path.replace
            def fail_new_alias(self, target):
                if self.name.startswith(f".{alias.name}.new-"):
                    raise OSError("injected alias promotion failure")
                return original_replace(self, target)

            with unittest.mock.patch.object(Path, "replace", new=fail_new_alias):
                with self.assertRaisesRegex(OSError, "injected alias promotion failure"):
                    module._atomic_promote_payload(stage, project, selected, alias)

            self.assertEqual((project / "old-runner").read_text(encoding="utf-8"), "old-payload")
            self.assertTrue(alias.is_symlink())
            self.assertEqual(alias.read_text(encoding="utf-8"), "old-payload")
            self.assertFalse((project / "new-runner").exists())
            self.assertFalse(list(root.glob(".*.backup-*")))
            self.assertFalse(list(root.glob(".*.new-*")))
            if stage.exists():
                module.shutil.rmtree(stage)

    def test_archive_payload_refuses_to_replace_a_directory_launcher_alias(self):
        spec = importlib.util.spec_from_file_location("install_upstream_atomic_alias", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = root / "rpcs3-payload"
            project.mkdir()
            old_binary = project / "old-runner"
            old_binary.write_text("old", encoding="utf-8")
            alias = root / "rpcs3"
            alias.mkdir()
            marker = alias / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            stage = Path(tempfile.mkdtemp(prefix=".rpcs3-stage-", dir=root))
            selected = stage / "new-runner"
            selected.write_text("new", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "launcher alias"):
                module._atomic_promote_payload(stage, project, selected, alias)

            self.assertEqual(old_binary.read_text(encoding="utf-8"), "old")
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
            module.shutil.rmtree(stage)


if __name__ == "__main__":
    unittest.main()
