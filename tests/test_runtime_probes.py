import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from runtime_probes import (
    env_flag,
    has_readonly_device_mapping,
    is_allowed_input_device,
    is_dashboard_summary_response,
    is_software_vulkan_renderer,
    parse_env_file,
)


class RuntimeProbeHelpersTests(unittest.TestCase):
    def test_flags_are_explicit_and_false_by_default(self):
        self.assertTrue(env_flag("REQUIRE", {"REQUIRE": "YeS"}))
        self.assertTrue(env_flag("REQUIRE", {"REQUIRE": "1"}))
        self.assertFalse(env_flag("REQUIRE", {"REQUIRE": "maybe"}))
        self.assertFalse(env_flag("REQUIRE", {}))

    def test_env_file_parser_does_not_execute_shell_or_interpolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text('# comment\nDISPLAY=:0\nINPUT="/dev/input/js0"\nBAD-KEY=x\nTOKEN=$(touch /tmp/should-not-exist)\n', encoding='utf-8')
            values = parse_env_file(path)
        self.assertEqual(values["DISPLAY"], ":0")
        self.assertEqual(values["INPUT"], "/dev/input/js0")
        self.assertEqual(values["TOKEN"], "$(touch /tmp/should-not-exist)")
        self.assertNotIn("BAD-KEY", values)

    def test_software_vulkan_renderer_is_distinguished_from_hardware(self):
        self.assertTrue(is_software_vulkan_renderer("deviceName = llvmpipe (LLVM 18.1)"))
        self.assertTrue(is_software_vulkan_renderer("deviceName = Mesa Lavapipe"))
        self.assertFalse(is_software_vulkan_renderer("deviceName = NVIDIA GeForce RTX 3060"))

    def test_dashboard_health_smoke_accepts_trusted_summary_contract(self):
        payload = {
            "project": "EmuStack",
            "emulator_count": 20,
            "launchers_ready": 3,
            "needs_attention": 5,
            "game_count": 2,
            "game_bytes": 4096,
            "active_process_count": 0,
            "process_count": 0,
            "install_report_count": 20,
            "generated_at": "2026-10-29T17:20:00+00:00",
            "security": {"privileged": False},
        }
        self.assertTrue(is_dashboard_summary_response(200, payload))
        self.assertFalse(is_dashboard_summary_response(503, payload))
        self.assertFalse(is_dashboard_summary_response(200, {**payload, "emulator_count": True}))
        self.assertFalse(is_dashboard_summary_response(200, {**payload, "generated_at": "not-a-timestamp"}))
        self.assertFalse(is_dashboard_summary_response(200, {**payload, "security": []}))

    def test_dashboard_health_smoke_rejects_minimal_untrusted_agent_health(self):
        self.assertFalse(is_dashboard_summary_response(200, {"healthy": True}))
        self.assertFalse(is_dashboard_summary_response(200, {"project": "other", "emulator_count": 20}))

    def test_input_device_paths_are_restricted_to_device_nodes(self):
        self.assertTrue(is_allowed_input_device("/dev/input/event4"))
        self.assertTrue(is_allowed_input_device("/dev/input/js0"))
        for path in ("/etc/passwd", "relative/path", "-r", "/dev/input/event1/../event2", ""):
            self.assertFalse(is_allowed_input_device(path), path)

    def test_controller_mapping_requires_same_device_readonly_and_no_mknod(self):
        base = {"Devices": [{"PathOnHost": "/dev/input/js0", "PathInContainer": "/dev/input/js0", "CgroupPermissions": "r"}]}
        self.assertTrue(has_readonly_device_mapping(base, "/dev/input/js0"))
        self.assertFalse(has_readonly_device_mapping(base, "/dev/input/js1"))
        self.assertFalse(has_readonly_device_mapping({"Devices": [{"PathOnHost": "/dev/input/js0", "PathInContainer": "/dev/input/js0", "CgroupPermissions": "rw"}]}, "/dev/input/js0"))
        self.assertFalse(has_readonly_device_mapping({"Devices": [{"PathOnHost": "/dev/input/js0", "PathInContainer": "/dev/input/js0", "CgroupPermissions": "rm"}]}, "/dev/input/js0"))


if __name__ == "__main__":
    unittest.main()
