import ast
import unittest
from unittest.mock import patch

import webapp


class IsolatedDashboardLogicTests(unittest.TestCase):
    def setUp(self):
        webapp.ACTIVE_ENVIRONMENT_RESERVATIONS.clear()

    def tearDown(self):
        webapp.ACTIVE_ENVIRONMENT_RESERVATIONS.clear()

    def _handler(self):
        handler_type = webapp.make_handler(
            lambda: {"emulators": []},
            lambda item: ("AVAILABLE", "/usr/bin/not-used-by-this-test"),
            lambda item: item,
        )
        return object.__new__(handler_type)

    def test_dashboard_source_policy_rejects_agent_source_even_with_spoofable_headers(self):
        trusted = frozenset({webapp.ipaddress.ip_address("172.28.1.1"), webapp.ipaddress.ip_address("172.28.2.1")})
        with patch.object(webapp, "CONTROL_TRUSTED_CLIENT_IPS", trusted):
            self.assertTrue(webapp._is_trusted_dashboard_client("127.0.0.1"))
            self.assertTrue(webapp._is_trusted_dashboard_client("::1"))
            self.assertTrue(webapp._is_trusted_dashboard_client("172.28.1.1"))
            self.assertFalse(webapp._is_trusted_dashboard_client("172.28.1.2"))
            self.assertFalse(webapp._is_trusted_dashboard_client("172.28.9.2"))
            self.assertFalse(webapp._is_trusted_dashboard_client("not-an-ip"))

    def test_active_environment_limit_counts_unique_environments_not_sessions(self):
        sessions = [
            {"environment_id": "rpcs3", "status": "running"},
            {"environment_id": "rpcs3", "status": "running"},
        ]
        with patch.object(webapp, "_agent_processes", return_value=sessions), \
             patch.object(webapp, "_known_environment_ids", return_value={"rpcs3", "pcsx2", "cemu"}), \
             patch.object(webapp, "_agent_request", return_value=(202, {"started": True})) as forward:
            status, payload = self._handler()._forward_launch("rpcs3", "/launch", {"game": "a.iso"})
            self.assertEqual(status, 202)
            self.assertTrue(payload["started"])
            forward.assert_called_once_with("rpcs3", "/launch", {"game": "a.iso"}, 3.0)

    def test_limit_blocks_a_third_distinct_environment(self):
        sessions = [
            {"environment_id": "rpcs3", "status": "running"},
            {"environment_id": "pcsx2", "status": "running"},
        ]
        with patch.object(webapp, "MAX_ACTIVE_ENVIRONMENTS", 2), \
             patch.object(webapp, "_agent_processes", return_value=sessions), \
             patch.object(webapp, "_known_environment_ids", return_value={"rpcs3", "pcsx2", "cemu"}), \
             patch.object(webapp, "_agent_request") as forward:
            status, payload = self._handler()._forward_launch("cemu", "/launch", {"game": "a.wud"})
            self.assertEqual(status, 429)
            self.assertFalse(payload["started"])
            forward.assert_not_called()

    def test_reservation_closes_race_between_two_new_environments(self):
        with patch.object(webapp, "MAX_ACTIVE_ENVIRONMENTS", 1), \
             patch.object(webapp, "_agent_processes", return_value=[]), \
             patch.object(webapp, "_known_environment_ids", return_value={"rpcs3", "pcsx2"}), \
             patch.object(webapp, "_agent_request", return_value=(503, {"started": False})):
            webapp.ACTIVE_ENVIRONMENT_RESERVATIONS["rpcs3"] = 1
            status, payload = self._handler()._forward_launch("pcsx2", "/launch", {})
            self.assertEqual(status, 429)
            self.assertFalse(payload["started"])

    def test_game_catalog_keeps_environment_identity(self):
        manifest = {"schema_version": 1, "environments": [
            {"id": "rpcs3", "name": "PS3", "directories": {}},
            {"id": "pcsx2", "name": "PS2", "directories": {}},
        ]}
        def fake_fetch(environment_id, route, timeout=1.2):
            if route == "/games":
                return (200, {"games": [{"path": "same.iso", "name": "same.iso", "size_bytes": 10, "size_label": "10 B"}]})
            return (200, {})
        with patch.object(webapp, "ISOLATED_MODE", True), \
             patch.object(webapp, "environment_manifest", return_value=manifest), \
             patch.object(webapp, "_fetch_agent_route", side_effect=fake_fetch):
            games = webapp.get_game_files()
        self.assertEqual({(game["environment_id"], game["path"]) for game in games}, {
            ("rpcs3", "same.iso"), ("pcsx2", "same.iso")
        })


    def test_dashboard_summary_has_single_effective_implementation(self):
        source = (webapp.ROOT / "webapp.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        summaries = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "summarize"]
        self.assertEqual(len(summaries), 1)

    def test_isolated_summary_uses_live_agents_and_handles_offline_profile(self):
        catalog = {"emulators": [{"id": "rpcs3"}, {"id": "pcsx2"}, {"id": "melonds"}]}
        envs = [
            {"id": "rpcs3", "online": True, "launch_available": True, "runtime_status": "AVAILABLE"},
            {"id": "pcsx2", "online": True, "launch_available": False, "runtime_status": "NOT INSTALLED"},
            {"id": "melonds", "online": False, "launch_available": False, "runtime_status": "AGENT_OFFLINE"},
        ]
        processes = [
            {"environment_id": "rpcs3", "status": "running"},
            {"environment_id": "rpcs3", "status": "exited"},
        ]
        games = [{"path": "homebrew.iso", "size_bytes": 2048}]
        def unexpected_status(_item):
            raise AssertionError("isolated summary must use agent health, not host binary discovery")

        with patch.object(webapp, "ISOLATED_MODE", True), \
             patch.object(webapp, "MAX_ACTIVE_ENVIRONMENTS", 2), \
             patch.object(webapp, "environment_records", return_value=envs) as records, \
             patch.object(webapp, "_agent_processes", return_value=processes), \
             patch.object(webapp, "get_game_files", return_value=games), \
             patch.object(webapp, "load_json", return_value={"items": {"rpcs3": {}, "pcsx2": {}}}):
            result = webapp.summarize(lambda: catalog, unexpected_status)

        records.assert_called_once_with(catalog, unexpected_status)
        self.assertEqual(result["emulator_count"], 3)
        self.assertEqual(result["environment_count"], 3)
        self.assertEqual(result["environments_online"], 2)
        self.assertEqual(result["launchers_ready"], 1)
        self.assertEqual(result["needs_attention"], 1)
        self.assertEqual(result["active_process_count"], 1)
        self.assertEqual(result["process_count"], 2)
        self.assertEqual(result["game_bytes"], 2048)
        self.assertEqual(result["install_report_count"], 2)
        self.assertEqual(result["max_active_environments"], 2)
        self.assertFalse(result["security"]["docker_socket_mounted"])
        self.assertIn("network_isolation", result["security"])
        self.assertIn("generated_at", result)

    def test_native_summary_still_reports_local_processes_and_missing_assets(self):
        catalog = {"emulators": [
            {"id": "rpcs3"}, {"id": "ppsspp"}, {"id": "xbox-one"},
        ]}
        status = {
            "rpcs3": ("AVAILABLE", "/bin/rpcs3"),
            "ppsspp": ("NOT INSTALLED", None),
            "xbox-one": ("NO STANDALONE RUNNER", None),
        }
        with patch.object(webapp, "ISOLATED_MODE", False), \
             patch.object(webapp, "environment_records") as records, \
             patch.object(webapp, "_process_snapshots", return_value=[{"status": "running"}, {"status": "exited"}]), \
             patch.object(webapp, "get_game_files", return_value=[]), \
             patch.object(webapp, "load_json", return_value={"items": "invalid"}):
            result = webapp.summarize(lambda: catalog, lambda item: status[item["id"]])

        records.assert_not_called()
        self.assertEqual(result["emulator_count"], 3)
        self.assertEqual(result["launchers_ready"], 1)
        self.assertEqual(result["needs_attention"], 1)
        self.assertEqual(result["active_process_count"], 1)
        self.assertEqual(result["process_count"], 2)
        self.assertEqual(result["install_report_count"], 0)
        self.assertNotIn("environment_count", result)
        self.assertNotIn("environments_online", result)
        self.assertFalse(result["security"]["privileged"])

    def test_isolated_summary_all_agents_offline_is_degraded_not_failed(self):
        envs = [
            {"id": "rpcs3", "online": False, "launch_available": False, "runtime_status": "AGENT_OFFLINE"},
        ]
        with patch.object(webapp, "ISOLATED_MODE", True), \
             patch.object(webapp, "environment_records", return_value=envs), \
             patch.object(webapp, "_agent_processes", return_value=[]), \
             patch.object(webapp, "get_game_files", return_value=[]), \
             patch.object(webapp, "load_json", return_value={}):
            summary = webapp.summarize(lambda: {"emulators": [{"id": "rpcs3"}]}, lambda _: ("UNKNOWN", None))
        self.assertEqual(summary["environment_count"], 1)
        self.assertEqual(summary["environments_online"], 0)
        self.assertEqual(summary["launchers_ready"], 0)
        self.assertEqual(summary["process_count"], 0)
        self.assertEqual(summary["install_report_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
