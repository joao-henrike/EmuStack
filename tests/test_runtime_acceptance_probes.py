import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("runtime_acceptance", ROOT / "scripts/runtime-acceptance.py")
runtime_acceptance = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(runtime_acceptance)


def fake_container(*, display=True, audio=True, input_device=True):
    environment = ["EMUSTACK_ENV_ID=rpcs3"]
    mounts = []
    if display:
        environment += ["DISPLAY=:0", "XAUTHORITY=/tmp/.Xauthority"]
        mounts += [{"Destination": "/tmp/.X11-unix"}, {"Destination": "/tmp/.Xauthority"}]
    if audio:
        environment += ["PULSE_SERVER=unix:/tmp/pulse/native"]
        mounts += [{"Destination": "/tmp/pulse/native"}]
    devices = []
    if input_device:
        devices = [{"PathOnHost": "/dev/input/js0", "PathInContainer": "/dev/input/js0", "CgroupPermissions": "r"}]
    return {"Id": "container-id", "Config": {"Env": environment}, "Mounts": mounts, "HostConfig": {"Devices": devices}}


class RuntimeAcceptanceProbeTests(unittest.TestCase):
    def test_required_host_integrations_pass_with_mocked_successful_container_probes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("EMUSTACK_INPUT_DEVICE=/dev/input/js0\nEMUSTACK_INPUT_ENV=rpcs3\n", encoding="utf-8")

            def fake_run(args, check=True, timeout=30):
                from subprocess import CompletedProcess
                command = " ".join(args)
                if "xdpyinfo" in command:
                    return CompletedProcess(args, 0, "name of display: :0", "")
                if "pactl" in command:
                    return CompletedProcess(args, 0, "Server Name: PulseAudio (on PipeWire)", "")
                if "vulkaninfo" in command:
                    return CompletedProcess(args, 0, "GPU0:\n deviceName = NVIDIA GeForce RTX 3060\n", "")
                if " test -r " in f" {command} ":
                    return CompletedProcess(args, 0, "", "")
                return CompletedProcess(args, 0, "", "")

            required = {name: "1" for name in (
                "EMUSTACK_REQUIRE_GUI", "EMUSTACK_REQUIRE_AUDIO", "EMUSTACK_REQUIRE_VULKAN",
                "EMUSTACK_REQUIRE_GPU", "EMUSTACK_REQUIRE_INPUT")}
            with patch.object(runtime_acceptance, "ROOT", root), patch.object(runtime_acceptance, "run", side_effect=fake_run), \
                 patch.dict(os.environ, required, clear=False):
                probes, warnings, errors = runtime_acceptance.runtime_hardware_probes(
                    {"rpcs3": fake_container()}, [{"id": "rpcs3"}])
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])
            self.assertTrue(all(probe["status"] == "PASS" for probe in probes), probes)

    def test_strict_requirements_fail_when_host_integrations_are_missing(self):
        def fake_run(args, check=True, timeout=30):
            from subprocess import CompletedProcess
            command = " ".join(args)
            if "vulkaninfo" in command:
                return CompletedProcess(args, 0, "GPU0:\n deviceName = llvmpipe (LLVM software renderer)\n", "")
            return CompletedProcess(args, 1, "", "not configured")

        required = {name: "1" for name in (
            "EMUSTACK_REQUIRE_GUI", "EMUSTACK_REQUIRE_AUDIO", "EMUSTACK_REQUIRE_VULKAN",
            "EMUSTACK_REQUIRE_GPU", "EMUSTACK_REQUIRE_INPUT")}
        with tempfile.TemporaryDirectory() as tmp, patch.object(runtime_acceptance, "ROOT", Path(tmp)), \
             patch.object(runtime_acceptance, "run", side_effect=fake_run), patch.dict(os.environ, required, clear=False):
            probes, warnings, errors = runtime_acceptance.runtime_hardware_probes(
                {"rpcs3": fake_container(display=False, audio=False, input_device=False)}, [{"id": "rpcs3"}])
        joined = "\n".join(errors)
        self.assertIn("display/X11", joined)
        self.assertIn("audio", joined)
        self.assertIn("GPU acceleration", joined)
        self.assertIn("controller device mapping", joined)
        self.assertFalse(warnings)
        self.assertEqual(next(p for p in probes if p["name"] == "Vulkan")["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
