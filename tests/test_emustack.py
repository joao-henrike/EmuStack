import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import emustack


class CatalogTests(unittest.TestCase):
    def test_all_twenty_projects_are_unique(self):
        data = emustack.catalog()
        items = data["emulators"]
        self.assertEqual(len(items), 20)
        ids = [item["id"] for item in items]
        self.assertEqual(len(ids), len(set(ids)))

    def test_release_lock_pins_only_verified_upstream_assets(self):
        catalog_payload = emustack.catalog()
        sha = "a" * 64
        report_payload = {"version": "0.7.1", "items": {
            "rpcs3": {"status": "installed", "repo": "RPCS3/rpcs3-binaries-linux", "version": "v0.0.35", "asset": "rpcs3.AppImage", "sha256": sha},
            "eden": {"status": "installed", "version": "Eden-Linux-v1-amd64-clang-pgo.AppImage", "asset": "Eden.AppImage", "url": "https://stable.eden-emu.dev/v1/Eden-Linux-v1-amd64-clang-pgo.AppImage", "sha256": sha},
            "pcsx2": {"status": "installed", "version": "Debian package", "source": "APT fallback", "binary": "/usr/bin/pcsx2"},
            "kytyps5": {"status": "installed", "version": "source build", "repo": "KytyPS5/KytyPS5", "asset": "source", "sha256": sha},
        }}
        lock = emustack.build_release_lock(report_payload, catalog_payload)
        self.assertTrue(lock["strict"])
        self.assertEqual(lock["items"]["rpcs3"], {
            "mode": "pinned", "repo": "RPCS3/rpcs3-binaries-linux", "tag": "v0.0.35",
            "asset": "rpcs3.AppImage", "sha256": sha,
        })
        self.assertEqual(lock["items"]["eden"]["mode"], "pinned-url")
        self.assertEqual(lock["items"]["pcsx2"]["mode"], "skip-upstream")
        self.assertIn("APT", lock["items"]["pcsx2"]["reason"])
        self.assertEqual(lock["items"]["kytyps5"]["mode"], "skip-upstream")
        self.assertIn("source", lock["items"]["kytyps5"]["reason"])
        self.assertEqual(len(lock["items"]), 20)

    def test_release_lock_rejects_unapproved_pinned_urls(self):
        payload = {"version": "0.7.1", "items": {"eden": {
            "status": "installed", "version": "v1", "asset": "file.AppImage",
            "url": "https://evil.example/file.AppImage", "sha256": "b" * 64,
        }}}
        lock = emustack.build_release_lock(payload, emustack.catalog())
        self.assertEqual(lock["items"]["eden"]["mode"], "skip-upstream")

    def test_every_project_has_reference_and_runtime(self):
        for item in emustack.catalog()["emulators"]:
            self.assertTrue(item["url"].startswith("https://"), item["id"])
            self.assertTrue(item.get("runtime"), item["id"])
            self.assertIn(item.get("game_arg"), {"append", "append-wine", "ui-only", "blocked"})

    def test_windows_and_research_projects_are_not_linux_launched(self):
        by_id = {item["id"]: item for item in emustack.catalog()["emulators"]}
        with patch.object(emustack, "catalog", return_value={"emulators": list(by_id.values())}):
            with self.assertRaises(SystemExit) as exc:
                emustack.launch("xbox-one", None, [])
            self.assertIn("não pode ser iniciado", str(exc.exception))
            with self.assertRaises(SystemExit) as exc:
                emustack.launch("xbox-series", None, [])
            self.assertIn("não pode ser iniciado", str(exc.exception))



    def test_ui_only_emulator_refuses_game_argument_instead_of_silently_ignoring_it(self):
        with tempfile.TemporaryDirectory() as tempdir:
            games = Path(tempdir) / "games"
            games.mkdir()
            game = games / "disc.iso"
            game.write_bytes(b"not-a-real-disc")
            entry = {"id": "xemu", "name": "xemu", "url": "https://xemu.app/", "runtime": "linux-native",
                     "game_arg": "ui-only", "binary_names": ["xemu"], "commands": []}
            with patch.object(emustack, "GAMES_DIR", games), \
                 patch.object(emustack, "catalog", return_value={"emulators": [entry]}), \
                 patch.object(emustack, "runtime_status", return_value=("AVAILABLE", "/usr/bin/xemu")), \
                 patch.dict(os.environ, {"DISPLAY": ":99"}), \
                 patch.object(emustack.subprocess, "run") as run:
                with self.assertRaises(SystemExit) as caught:
                    emustack.launch("xemu", "disc.iso", [])
                self.assertIn("não aceita este caminho", str(caught.exception))
                run.assert_not_called()

    def test_rpcs3_pkg_uses_install_mode_and_license_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as tempdir:
            games = Path(tempdir) / "games"
            games.mkdir()
            pkg = games / "title.pkg"
            pkg.write_bytes(b"test pkg placeholder")
            rap = games / "license.rap"
            rap.write_bytes(b"test license placeholder")
            with patch.object(emustack, "GAMES_DIR", games), \
                 patch.object(emustack, "catalog", return_value={"emulators": [
                     {"id": "rpcs3", "name": "RPCS3", "url": "https://rpcs3.net/", "runtime": "linux-native",
                      "game_arg": "append", "binary_names": ["rpcs3"], "commands": []}
                 ]}), \
                 patch.object(emustack, "runtime_status", return_value=("AVAILABLE", "/usr/bin/rpcs3")), \
                 patch.dict(os.environ, {"DISPLAY": ":99"}), \
                 patch.object(emustack.subprocess, "run", return_value=type("Result", (), {"returncode": 0})()) as run:
                result = emustack.launch("rpcs3", "title.pkg", [])
                self.assertEqual(result, 0)
                argv = run.call_args.args[0]
                self.assertEqual(argv[:3], ["/usr/bin/rpcs3", "--installpkg", str(pkg)])
                with self.assertRaises(SystemExit) as caught:
                    emustack.launch("rpcs3", "license.rap", [])
                self.assertIn("licença/suporte", str(caught.exception))
                self.assertEqual(run.call_count, 1)

    def test_external_paths_are_blocked_by_default(self):
        with tempfile.TemporaryDirectory() as tempdir:
            outside = Path(tempdir) / "game.rom"
            outside.write_text("test", encoding="utf-8")
            with patch.dict(os.environ, {"EMUSTACK_ALLOW_EXTERNAL_GAMES": "0"}):
                with self.assertRaises(SystemExit) as exc:
                    emustack.safe_game_path(str(outside))
                self.assertIn("por segurança", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
