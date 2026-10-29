import io
import json
import os
import subprocess
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import emustack
import webapp


class FakeProcess:
    def __init__(self, pid=88881, output=b"fake launcher output\\n", exit_code=None):
        self.pid = pid
        self.stdout = io.BytesIO(output)
        self.returncode = exit_code

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9


class WebAppTests(unittest.TestCase):
    def setUp(self):
        with webapp.PROCESS_LOCK:
            for record in webapp.PROCESS_REGISTRY.values():
                process = record.get("process")
                if process and process.poll() is None:
                    try:
                        os.killpg(process.pid, 15)
                    except OSError:
                        try:
                            process.terminate()
                        except OSError:
                            pass
            webapp.PROCESS_REGISTRY.clear()
            webapp.LAUNCH_RESERVATIONS = 0
            webapp.ACTIVE_ENVIRONMENT_RESERVATIONS.clear()
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.games = self.root / "games"
        self.games.mkdir()
        self.log_dir = self.root / "logs"
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            webapp.make_handler(
                emustack.catalog,
                lambda item: ("AVAILABLE", "/usr/bin/example-emulator"),
                lambda game: Path(game),
            ),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        with webapp.PROCESS_LOCK:
            for record in webapp.PROCESS_REGISTRY.values():
                process = record.get("process")
                if process and process.poll() is None:
                    try:
                        os.killpg(process.pid, 15)
                    except OSError:
                        try:
                            process.terminate()
                        except OSError:
                            pass
            webapp.PROCESS_REGISTRY.clear()
            webapp.LAUNCH_RESERVATIONS = 0
            webapp.ACTIVE_ENVIRONMENT_RESERVATIONS.clear()
        self.tempdir.cleanup()

    def post_json(self, path, payload):
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            self.base + path,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "X-EmuStack-Request": "1"},
        )
        return urlopen(request, timeout=3)

    def test_catalog_and_docs_api(self):
        with urlopen(self.base + "/api/catalog", timeout=3) as response:
            catalog = json.load(response)
        self.assertEqual(len(catalog["emulators"]), 20)
        self.assertTrue(all("runtime_status" in item for item in catalog["emulators"]))
        self.assertEqual(catalog["version"], "0.7.1")
        with urlopen(self.base + "/api/docs", timeout=3) as response:
            docs = json.load(response)
        self.assertGreaterEqual(len(docs["documents"]), 6)
        self.assertIn("readme", {doc["id"] for doc in docs["documents"]})
        self.assertIn("ORIGINAL_SYSTEM_UI", {doc["id"] for doc in docs["documents"]})

    def test_console_systems_api_exposes_native_and_unsupported_profiles(self):
        with urlopen(self.base + "/api/console-systems", timeout=3) as response:
            data = json.load(response)
        self.assertEqual(data["version"], "0.7.1")
        self.assertGreaterEqual(len(data["systems"]), 18)
        by_id = {item["id"]: item for item in data["systems"]}
        self.assertIn("can_boot_original", by_id["ps3-xmb"])
        self.assertEqual(by_id["ps5-system"]["state"], "unsupported")
        self.assertFalse(by_id["ps5-system"]["can_boot_original"])
        self.assertIn("xemu", by_id["xbox-original-dashboard"]["details"].lower()) 
    def test_install_report_api_returns_structured_per_profile_evidence(self):
        report_path = self.root / "install-report.json"
        payload = {
            "project": "EmuStack",
            "schema_version": 2,
            "items": {
                "rpcs3": {
                    "profile_id": "rpcs3",
                    "status": "installed",
                    "installation_status": "installed",
                    "evidence": {"host_architecture": "x86_64", "sha256_actual": "a" * 64},
                    "execution_test": {"status": "not-run", "reason": "GUI execution belongs to host validation."},
                    "runtime_test": {"status": "not-run", "reason": "Boot has not been tested."},
                }
            },
        }
        report_path.write_text(json.dumps(payload), encoding="utf-8")
        with patch.object(webapp, "INSTALL_REPORT", report_path):
            with urlopen(self.base + "/api/report", timeout=3) as response:
                result = json.load(response)

        self.assertTrue(result["available"])
        self.assertEqual(result["report"]["schema_version"], 2)
        item = result["report"]["items"]["rpcs3"]
        self.assertEqual(item["evidence"]["host_architecture"], "x86_64")
        self.assertEqual(item["execution_test"]["status"], "not-run")
        self.assertEqual(item["runtime_test"]["status"], "not-run")

    def test_install_report_api_explains_when_report_is_missing(self):
        report_path = self.root / "missing-install-report.json"
        with patch.object(webapp, "INSTALL_REPORT", report_path):
            with urlopen(self.base + "/api/report", timeout=3) as response:
                result = json.load(response)

        self.assertFalse(result["available"])
        self.assertIn("mensagem", result.get("message", "").lower() or "mensagem" if False else result["message"].lower())


    def test_console_system_boot_starts_ps2_bios_profile_through_managed_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            bios_root = Path(tmp)
            bios_dir = bios_root / "pcsx2"
            bios_dir.mkdir()
            (bios_dir / "bios-fixture.bin").write_bytes(b"fixture only; not an actual console BIOS")
            process = FakeProcess(pid=88884, output=b"boot-system invoked\n")
            with patch.dict(os.environ, {"DISPLAY": ":99"}), \
                 patch.object(webapp.console_modes, "BIOS_DIR", bios_root), \
                 patch.object(webapp, "LOG_DIR", self.log_dir), \
                 patch.object(webapp.subprocess, "Popen", return_value=process) as popen:
                with self.post_json("/api/console-systems/launch", {"system": "ps2-bios-menu", "action": "boot"}) as response:
                    self.assertEqual(response.status, 202)
                    result = json.load(response)
                self.assertTrue(result["started"])
                self.assertEqual(result["system"], "ps2-bios-menu")
                argv = popen.call_args.args[0]
                self.assertIn("boot-system", argv)
                self.assertIn("ps2-bios-menu", argv)

    def test_console_system_boot_rejects_unsupported_full_systems(self):
        with patch.dict(os.environ, {"DISPLAY": ":99"}), patch.object(webapp.subprocess, "Popen") as popen:
            with self.assertRaises(HTTPError) as caught:
                self.post_json("/api/console-systems/launch", {"system": "ps5-system", "action": "boot"})
            self.assertEqual(caught.exception.code, 409)
            body = json.loads(caught.exception.read())
            self.assertIn("boot automático", body["error"])
            popen.assert_not_called()

    def test_game_scan_ignores_hidden_archives_and_non_game_json(self):
        (self.games / "demo.gba").write_bytes(b"gba")
        (self.games / "archive.zip").write_bytes(b"zip")
        (self.games / "metadata.json").write_text("{}", encoding="utf-8")
        (self.games / "notes.txt").write_text("not a game", encoding="utf-8")
        hidden = self.games / ".private"
        hidden.mkdir()
        (hidden / "hidden.iso").write_bytes(b"iso")
        with patch.object(webapp, "GAMES_DIR", self.games):
            items = webapp.get_game_files()
        self.assertEqual([item["path"] for item in items], ["demo.gba"])
        self.assertEqual(items[0]["size_bytes"], 3)

    def test_sources_api_catalog_has_official_urls(self):
        source_path = Path(__file__).resolve().parents[1] / "game-sources.json"
        data = json.loads(source_path.read_text(encoding="utf-8"))
        category_ids = {category["id"] for category in data["categories"]}
        source_ids = {source["id"] for source in data["sources"]}
        self.assertGreaterEqual(len(data["sources"]), 14)
        for source in data["sources"]:
            self.assertTrue(source["url"].startswith("https://"), source["id"])
            self.assertIn(source["category"], category_ids)
            self.assertIsInstance(source["platforms"], list)
        self.assertIn("pdroms", source_ids)
        self.assertIn("ppsspp-official-demos", source_ids)
        self.assertIn("itch-nes-roms", source_ids)
        self.assertFalse(data["automation_policy"]["automatic_game_downloads"])
        self.assertFalse(data["automation_policy"]["automatic_game_installation"])
        environments = json.loads((source_path.parent / "environments.json").read_text(encoding="utf-8"))
        environment_ids = {item["id"] for item in environments["environments"]}
        guidance_ids = {item["environment_id"] for item in data["platform_guidance"]}
        self.assertEqual(guidance_ids, environment_ids)
        for mapping in data["platform_guidance"]:
            self.assertIsInstance(mapping["guidance"], str)
            self.assertTrue(mapping["guidance"])
            self.assertTrue(set(mapping["source_ids"]).issubset(source_ids), mapping["environment_id"])

    def test_source_catalog_has_console_filters_and_rights_notice(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="source-platform-tabs"', page)
        self.assertIn('id="source-platform-note"', page)
        self.assertIn("state.sources.platform_guidance", script)
        self.assertIn("selectedSourcePlatform", script)
        self.assertIn("normalmente publicam código e binários do emulador, não jogos", script)

    def test_launch_dialog_contract_handles_no_recommendation(self):
        source = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("window.EmuStackLaunch.recommendEmulatorForGame(gamePath)", source)
        self.assertIn("first?.game_arg", source)
        self.assertNotIn("${first.game_arg", source)
        self.assertNotIn("[['.pkg','.rap','.self'], 'rpcs3']", source)
        page = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
        self.assertLess(page.index("/assets/launch-utils.js"), page.index("/assets/app.js"))

    def test_console_system_interface_has_native_boot_ui_and_clear_capability_language(self):
        root = Path(__file__).resolve().parents[1]
        page = (root / "web" / "index.html").read_text(encoding="utf-8")
        script = (root / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn('data-view="consoles"', page)
        self.assertIn('id="view-consoles"', page)
        self.assertIn('id="console-system-grid"', page)
        self.assertIn("renderConsoleSystems", script)
        self.assertIn("/api/console-systems", script)
        self.assertIn("data-system-action", script)
        self.assertIn("dashboard do HDD", script)
        self.assertIn("não desenha dashboards falsos", page)

    def test_launch_requires_graphical_session_instead_of_false_success(self):
        with patch.dict(os.environ, {"DISPLAY": ""}), patch.object(webapp.subprocess, "Popen") as popen:
            with self.assertRaises(HTTPError) as caught:
                self.post_json("/api/launch", {"emulator": "rpcs3", "game": None})
            self.assertEqual(caught.exception.code, 409)
            body = json.loads(caught.exception.read())
            self.assertIn("sessão gráfica", body["error"])
            popen.assert_not_called()

    def test_launch_tracks_process_and_exposes_bounded_logs(self):
        process = FakeProcess(pid=88882)
        with patch.dict(os.environ, {"DISPLAY": ":99"}), patch.object(webapp, "LOG_DIR", self.log_dir), patch.object(webapp.subprocess, "Popen", return_value=process):
            with self.post_json("/api/launch", {"emulator": "rpcs3", "game": None}) as response:
                self.assertEqual(response.status, 202)
                result = json.load(response)
            self.assertTrue(result["started"])
            self.assertEqual(result["pid"], process.pid)
            with urlopen(self.base + "/api/processes", timeout=3) as response:
                sessions = json.load(response)
            self.assertEqual(sessions["active"], 1)
            self.assertEqual(sessions["processes"][0]["emulator"], "rpcs3")
            with urlopen(self.base + f"/api/processes/{process.pid}/log", timeout=3) as response:
                log = json.load(response)
            self.assertIn("fake launcher output", log["log"])

    def test_immediate_launch_failure_is_not_reported_as_success(self):
        process = FakeProcess(pid=88883, output=b"missing dependency", exit_code=127)
        with patch.dict(os.environ, {"DISPLAY": ":99"}), patch.object(webapp, "LOG_DIR", self.log_dir), patch.object(webapp.subprocess, "Popen", return_value=process):
            with self.assertRaises(HTTPError) as caught:
                self.post_json("/api/launch", {"emulator": "rpcs3", "game": None})
            self.assertEqual(caught.exception.code, 502)
            body = json.loads(caught.exception.read())
            self.assertFalse(body["started"])
            self.assertEqual(body["exit_code"], 127)
            self.assertIn("missing dependency", body["log"])


    def test_rpcs3_license_file_is_not_launched_as_a_game(self):
        with patch.dict(os.environ, {"DISPLAY": ":99"}), patch.object(webapp, "LOG_DIR", self.log_dir), patch.object(webapp.subprocess, "Popen") as popen:
            with self.assertRaises(HTTPError) as caught:
                self.post_json("/api/launch", {"emulator": "rpcs3", "game": "license.rap"})
            self.assertEqual(caught.exception.code, 400)
            self.assertIn("licença", json.loads(caught.exception.read())["error"])
            popen.assert_not_called()

    def test_non_object_json_body_is_rejected(self):
        request = Request(
            self.base + "/api/launch",
            data=b"[]",
            method="POST",
            headers={"Content-Type": "application/json", "X-EmuStack-Request": "1"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=3)
        self.assertEqual(caught.exception.code, 400)
        self.assertIn("objeto", json.loads(caught.exception.read())["error"])

    def test_stop_managed_process_group(self):
        process = subprocess.Popen(["sleep", "30"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        log_path = self.log_dir / "sleep.log"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path.write_text("sleep test", encoding="utf-8")
        record = {
            "process": process,
            "emulator": "test-process",
            "emulator_name": "Test process",
            "game": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "log_path": str(log_path),
        }
        with webapp.PROCESS_LOCK:
            webapp.PROCESS_REGISTRY[process.pid] = record
        with self.post_json("/api/processes/stop", {"pid": process.pid}) as response:
            payload = json.load(response)
        self.assertTrue(payload["stopped"])
        self.assertIsNotNone(process.poll())
        self.assertEqual(payload["process"]["status"], "stopped")
        if process.stdout:
            process.stdout.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
