import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SETUP = PROJECT / "scripts" / "host-setup.sh"


class HostSetupTests(unittest.TestCase):
    def _run_setup(self, gui: bool, preserve_flags: bool = False):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name) / "EmuStack"
        (root / "scripts").mkdir(parents=True)
        (root / "scripts" / "host-setup.sh").write_bytes(SETUP.read_bytes())
        os.chmod(root / "scripts" / "host-setup.sh", 0o755)
        home = Path(td.name) / "home"
        home.mkdir()
        runtime = Path(td.name) / "runtime"
        runtime.mkdir()
        xauth = home / ".Xauthority"
        xauth.write_bytes(b"test-auth")
        if preserve_flags:
            (root / ".env").write_text("BUILD_KYTYPS5=0\nKYTYPS5_REF=KytyPS5-test-ref\nKYTYPS5_EXPECTED_SHORT=123abcd\nAPT_SNAPSHOT_TIMESTAMP=20261027T000000Z\nDEBIAN_BASE_IMAGE=debian:trixie-slim@sha256:test\nINSTALL_UPSTREAM=0\nEMUSTACK_CPU_LIMIT=6\nEMUSTACK_MEMORY_LIMIT=8g\nEMUSTACK_PIDS_LIMIT=256\nEMUSTACK_CLI_CPU_LIMIT=2\nEMUSTACK_CLI_MEMORY_LIMIT=2g\nEMUSTACK_CLI_PIDS_LIMIT=128\n", encoding="utf-8")
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["XDG_RUNTIME_DIR"] = str(runtime)
        env.pop("PULSE_SERVER", None)
        x11_socket_dir = Path(td.name) / "X11-unix"
        if gui:
            x11_socket_dir.mkdir()
            env["DISPLAY"] = ":99"
            env["XAUTHORITY"] = str(xauth)
            env["X11_SOCKET_DIR"] = str(x11_socket_dir)
        else:
            env.pop("DISPLAY", None)
            env.pop("XAUTHORITY", None)
        result = subprocess.run([str(root / "scripts" / "host-setup.sh")], cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        return td, root, result



    def test_compose_sets_resource_limits_and_loopback_only_dashboard(self):
        compose = (PROJECT / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn('cpus: ${EMUSTACK_CLI_CPU_LIMIT:-2}', compose)
        self.assertIn('mem_limit: ${EMUSTACK_CLI_MEMORY_LIMIT:-2g}', compose)
        self.assertIn('pids_limit: ${EMUSTACK_CLI_PIDS_LIMIT:-128}', compose)
        self.assertIn('cpus: ${EMUSTACK_CPU_LIMIT:-2}', compose)
        self.assertIn('mem_limit: ${EMUSTACK_MEMORY_LIMIT:-1g}', compose)
        self.assertIn('pids_limit: ${EMUSTACK_PIDS_LIMIT:-256}', compose)
        self.assertIn('127.0.0.1:8765:8765', compose)
        self.assertIn('internal: true', compose)
        self.assertNotIn('/var/run/docker.sock', compose)
        self.assertIn('EMUSTACK_ISOLATED_MODE: "1"', compose)

    def test_controller_mapping_is_opt_in_and_restricted_to_one_device(self):
        source = SETUP.read_text(encoding="utf-8")
        self.assertIn("EMUSTACK_INPUT_DEVICE", source)
        self.assertIn("^/dev/input/(event|js)[0-9]+$", source)
        self.assertIn('f"{input_device}:{input_device}:r"', source)
        self.assertIn('if [ "$GUI_ENABLED" -eq 1 ] || [ -n "$INPUT_DEVICE" ]; then', source)

    def test_build_script_includes_host_override_and_optional_nvidia_overlay(self):
        source = (PROJECT / "scripts" / "build-and-audit.sh").read_text(encoding="utf-8")
        self.assertIn('compose+=(-f compose.override.yaml)', source)
        self.assertIn('compose+=(-f compose.nvidia.yaml)', source)
        self.assertIn('./scripts/validate-project.sh', source)

    def test_headless_setup_succeeds_without_gui_override(self):
        td, root, result = self._run_setup(gui=False)
        try:
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertFalse((root / "compose.override.yaml").exists())
            env_text = (root / ".env").read_text(encoding="utf-8")
            self.assertIn("PUID=", env_text)
            self.assertNotIn("DISPLAY=", env_text)
            token_lines = [line for line in env_text.splitlines() if line.startswith("EMUSTACK_AGENT_TOKEN_")]
            tokens = [line.split("=", 1)[1] for line in token_lines]
            self.assertEqual(len(token_lines), 20)
            self.assertEqual(len(set(tokens)), 20)
            self.assertTrue(all(__import__("re").fullmatch(r"[a-f0-9]{64}", token) for token in tokens))
            self.assertEqual((root / ".env").stat().st_mode & 0o777, 0o600)
            for env_id in "kytyps5 shadps4 rpcs3 duckstation pcsx2 ppsspp vita3k xbox-one xenia-canary xbox-series xemu eden cemu dolphin azahar melonds mgba mupen64plus bsnes mesen".split():
                self.assertTrue((root / "data" / "environments" / env_id / "games").is_dir())
                self.assertTrue((root / "data" / "environments" / env_id / "home").is_dir())
        finally:
            td.cleanup()

    def test_setup_refuses_environment_root_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "EmuStack"
            (root / "scripts").mkdir(parents=True)
            setup = root / "scripts" / "host-setup.sh"
            setup.write_bytes(SETUP.read_bytes())
            os.chmod(setup, 0o755)
            env_root = root / "data" / "environments"
            env_root.mkdir(parents=True)
            real = env_root / "rpcs3"
            real.mkdir()
            (env_root / "xemu").symlink_to(real, target_is_directory=True)
            result = subprocess.run([str(setup)], cwd=root, env={**os.environ, "HOME": td}, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", (result.stdout + result.stderr).lower())

    def test_agent_tokens_are_unique_and_preserved_on_rerun(self):
        td, root, result = self._run_setup(gui=False)
        try:
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            env_path = root / ".env"
            first = {line.split("=", 1)[0]: line.split("=", 1)[1] for line in env_path.read_text(encoding="utf-8").splitlines() if line.startswith("EMUSTACK_AGENT_TOKEN_")}
            self.assertEqual(len(first), 20)
            self.assertEqual(len(set(first.values())), 20)
            rerun = subprocess.run([str(root / "scripts" / "host-setup.sh")], cwd=root, env={**os.environ, "HOME": str(root.parent / "home")}, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            self.assertEqual(rerun.returncode, 0, msg=rerun.stdout + rerun.stderr)
            second = {line.split("=", 1)[0]: line.split("=", 1)[1] for line in env_path.read_text(encoding="utf-8").splitlines() if line.startswith("EMUSTACK_AGENT_TOKEN_")}
            self.assertEqual(second, first)
            self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)
        finally:
            td.cleanup()

    def test_graphical_setup_generates_valid_compose_json_and_preserves_build_flags(self):
        td, root, result = self._run_setup(gui=True, preserve_flags=True)
        try:
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            override_path = root / "compose.override.yaml"
            self.assertTrue(override_path.is_file())
            config = json.loads(override_path.read_text(encoding="utf-8"))
            expected_envs = {
                "env-" + env_id for env_id in
                "kytyps5 shadps4 rpcs3 duckstation pcsx2 ppsspp vita3k xbox-one xenia-canary xbox-series xemu eden cemu dolphin azahar melonds mgba mupen64plus bsnes mesen".split()
            }
            self.assertEqual(set(config["services"]), expected_envs)
            for service in config["services"].values():
                self.assertEqual(service["environment"]["DISPLAY"], ":99")
                self.assertTrue(any(mount["target"] == "/tmp/.Xauthority" for mount in service["volumes"]))
                self.assertTrue(any(mount["target"] == "/tmp/.X11-unix" for mount in service["volumes"]))
                self.assertNotIn("dashboard", config["services"])
            env_text = (root / ".env").read_text(encoding="utf-8")
            self.assertIn("BUILD_KYTYPS5=0", env_text)
            self.assertIn("KYTYPS5_REF=KytyPS5-test-ref", env_text)
            self.assertIn("KYTYPS5_EXPECTED_SHORT=123abcd", env_text)
            self.assertIn("APT_SNAPSHOT_TIMESTAMP=20261027T000000Z", env_text)
            self.assertIn("DEBIAN_BASE_IMAGE=debian:trixie-slim@sha256:test", env_text)
            self.assertIn("INSTALL_UPSTREAM=0", env_text)
            self.assertIn("EMUSTACK_CPU_LIMIT=6", env_text)
            self.assertIn("EMUSTACK_MEMORY_LIMIT=8g", env_text)
            self.assertIn("EMUSTACK_PIDS_LIMIT=256", env_text)
            self.assertIn("EMUSTACK_CLI_CPU_LIMIT=2", env_text)
            self.assertIn("EMUSTACK_CLI_MEMORY_LIMIT=2g", env_text)
            self.assertIn("EMUSTACK_CLI_PIDS_LIMIT=128", env_text)
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
