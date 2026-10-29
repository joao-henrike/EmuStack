from pathlib import Path
import unittest
from unittest.mock import patch

import webapp


class SummarizeContractTests(unittest.TestCase):
    def test_module_has_only_one_summarize_definition(self):
        source = Path(webapp.__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count("\ndef summarize("), 1)

    def test_isolated_mode_reports_agent_and_environment_metrics(self):
        catalog = {"emulators": [{"id": "duckstation", "name": "DuckStation"}]}
        environments = [
            {"id": "duckstation", "launch_available": True, "online": True, "runtime_status": "AVAILABLE"},
            {"id": "pcsx2", "launch_available": False, "online": True, "runtime_status": "DEGRADED"},
            {"id": "rpcs3", "launch_available": False, "online": False, "runtime_status": "OFFLINE"},
        ]
        processes = [{"status": "running"}, {"status": "exited"}]
        games = [{"size_bytes": 10}, {"size_bytes": 25}]

        with (
            patch.object(webapp, "ISOLATED_MODE", True),
            patch.object(webapp, "environment_records", return_value=environments),
            patch.object(webapp, "_agent_processes", return_value=processes),
            patch.object(webapp, "_process_snapshots", side_effect=AssertionError("host registry used in isolated mode")),
            patch.object(webapp, "get_game_files", return_value=games),
            patch.object(webapp, "load_json", return_value={"items": {"duckstation": {"status": "installed"}}}),
        ):
            summary = webapp.summarize(lambda: catalog, lambda _item: ("AVAILABLE", "/opt/example"))

        self.assertEqual(summary["environment_count"], 3)
        self.assertEqual(summary["environments_online"], 2)
        self.assertEqual(summary["launchers_ready"], 1)
        self.assertEqual(summary["needs_attention"], 1)
        self.assertEqual(summary["active_process_count"], 1)
        self.assertEqual(summary["process_count"], 2)
        self.assertEqual(summary["game_count"], 2)
        self.assertEqual(summary["game_bytes"], 35)
        self.assertEqual(summary["install_report_count"], 1)
        self.assertEqual(summary["max_active_environments"], webapp.MAX_ACTIVE_ENVIRONMENTS)
        self.assertFalse(summary["security"]["docker_socket_mounted"])

    def test_host_mode_uses_host_process_registry_and_preserves_summary_fields(self):
        catalog = {
            "emulators": [
                {"id": "duckstation", "name": "DuckStation"},
                {"id": "pcsx2", "name": "PCSX2"},
            ]
        }
        processes = [{"status": "running"}, {"status": "failed"}]

        with (
            patch.object(webapp, "ISOLATED_MODE", False),
            patch.object(webapp, "_process_snapshots", return_value=processes),
            patch.object(webapp, "_agent_processes", side_effect=AssertionError("agent process list used in host mode")),
            patch.object(webapp, "get_game_files", return_value=[]),
            patch.object(webapp, "load_json", return_value={"items": {}}),
        ):
            statuses = {"duckstation": ("AVAILABLE", "/opt/duckstation"), "pcsx2": ("NEEDS BIOS", None)}
            summary = webapp.summarize(lambda: catalog, lambda item: statuses[item["id"]])

        self.assertEqual(summary["emulator_count"], 2)
        self.assertEqual(summary["launchers_ready"], 1)
        self.assertEqual(summary["needs_attention"], 1)
        self.assertEqual(summary["active_process_count"], 1)
        self.assertEqual(summary["process_count"], 2)
        self.assertFalse(summary["install_report_present"])
        self.assertNotIn("environment_count", summary)


if __name__ == "__main__":
    unittest.main()
