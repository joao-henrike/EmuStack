import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from runtime_probes import env_flag, has_readonly_device_mapping, is_allowed_input_device, is_software_vulkan_renderer, parse_env_file


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

    def test_software_only_vulkan_is_distinguished_from_hardware_and_mixed_devices(self):
        self.assertTrue(is_software_vulkan_renderer("deviceName = llvmpipe (LLVM 18.1)"))
        self.assertTrue(is_software_vulkan_renderer("deviceName = Mesa Lavapipe"))
        self.assertFalse(is_software_vulkan_renderer("deviceName = NVIDIA GeForce RTX 3060"))
        mixed_devices = (
            "GPU0:\n deviceName = NVIDIA GeForce RTX 4050 Laptop GPU\\n"
            "GPU1:\n deviceName = llvmpipe (LLVM 19.1.7, 256 bits)\\n"
        )
        self.assertFalse(is_software_vulkan_renderer(mixed_devices))
        software_devices = (
            "GPU0:\n deviceName = llvmpipe (LLVM 19.1.7, 256 bits)\\n"
            "GPU1:\n deviceName = Mesa Lavapipe\\n"
        )
        self.assertTrue(is_software_vulkan_renderer(software_devices))

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
