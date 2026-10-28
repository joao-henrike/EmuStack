import importlib.util
import json
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
            self.assertEqual(data["items"]["xbox-one"]["status"], "unsupported-no-runner")
            self.assertEqual(data["items"]["xbox-series"]["status"], "unsupported-no-runner")

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


if __name__ == "__main__":
    unittest.main()
