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
            self.assertTrue(webapp._is_trusted_control_client("::1"))
            self.assertTrue(webapp._is_trusted_control_client("172.28.1.1"))
            self.assertFalse(webapp._is_trusted_control_client("172.28.1.2"))
            self.assertFalse(webapp._is_trusted_control_client("172.28.9.2"))
            self.assertFalse(webapp._is_trusted_control_client("not-an-ip"))

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
