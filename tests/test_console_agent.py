import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import console_agent


class ConsoleAgentIsolationTests(unittest.TestCase):
    def test_profile_comes_only_from_fixed_manifest_environment(self):
        with patch.object(console_agent, "ENV_ID", "rpcs3"):
            profile = console_agent._profile()
            self.assertEqual(profile["id"], "rpcs3")
        with patch.object(console_agent, "ENV_ID", "dashboard"):
            with self.assertRaises(RuntimeError):
                console_agent._profile()

    def test_game_path_must_be_relative_and_inside_this_environment(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "safe.iso").write_bytes(b"fixture")
            with patch.object(console_agent, "GAMES_DIR", root):
                path, rel = console_agent._safe_relative_game("safe.iso")
                self.assertEqual(path, root / "safe.iso")
                self.assertEqual(rel, "safe.iso")
                for value in ("../outside.iso", "/etc/passwd", "nested/../../x.iso", "bad\\path.iso", ""):
                    with self.subTest(value=value), self.assertRaises(ValueError):
                        console_agent._safe_relative_game(value)

    def test_game_path_rejects_symlink_even_when_target_is_inside(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "real.iso").write_bytes(b"fixture")
            (root / "shortcut.iso").symlink_to(root / "real.iso")
            with patch.object(console_agent, "GAMES_DIR", root):
                with self.assertRaises(ValueError):
                    console_agent._safe_relative_game("shortcut.iso")

    def test_rpcs3_support_license_files_are_never_launchable(self):
        with patch.object(console_agent, "ENV_ID", "rpcs3"), \
             patch.object(console_agent, "_emulator", return_value={"id": "rpcs3", "name": "RPCS3", "game_arg": "append"}), \
             patch.object(console_agent, "_runtime", return_value=("AVAILABLE", "/opt/rpcs3")), \
             patch.dict(os.environ, {"DISPLAY": ":99"}), \
             patch.object(console_agent, "_start") as starter:
            status, result = console_agent._start_emulator("license.rap")
            self.assertEqual(status, 400)
            self.assertFalse(result["started"])
            starter.assert_not_called()

    def test_system_status_checks_only_this_environment_emulator(self):
        profile = {
            "id": "xbox360-system", "name": "Xbox 360 Dashboard",
            "emulator_ids": ["xenia-canary", "xbox-series"],
            "boot_strategy": "unsupported", "details": "Full dashboard boot is unsupported.",
        }
        own_emulator = {"id": "xbox-series", "name": "Xbox Series (bloqueado)", "game_arg": "blocked"}
        catalog = {"schema_version": 1, "emulators": [
            {"id": "xenia-canary", "name": "Xenia Canary"}, own_emulator,
        ]}
        with patch.object(console_agent, "ENV_ID", "xbox-series"), \
             patch.object(console_agent, "_catalog", return_value=catalog), \
             patch.object(console_agent, "_emulator", return_value=own_emulator), \
             patch.object(console_agent.emustack, "runtime_status", side_effect=lambda item: ("AVAILABLE", "/bin/xenia-canary") if item["id"] == "xenia-canary" else ("NO_LINUX_EMULATOR_BIN", None)) as runtime:
            state = console_agent._resolve_system_for_this_environment(profile)
        self.assertFalse(state["binary_found"])
        self.assertFalse(state["can_boot_original"])
        runtime.assert_called_once_with(own_emulator)

    def test_blocked_emulator_does_not_invoke_process(self):
        with patch.object(console_agent, "ENV_ID", "xbox-one"), \
             patch.object(console_agent, "_emulator", return_value={"id": "xbox-one", "name": "Xbox One (bloqueado)", "game_arg": "blocked", "notes": "No supported runner"}), \
             patch.object(console_agent.subprocess, "Popen") as popen:
            status, result = console_agent._start_emulator()
            self.assertEqual(status, 409)
            self.assertFalse(result["started"])
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
