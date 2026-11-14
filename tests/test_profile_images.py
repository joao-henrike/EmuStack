"""Contracts for per-profile Docker targets and isolated APT inventory."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-upstream.py"
PROFILE_TARGETS = {
    "dolphin": ("local/emustack-dolphin:0.7.1", "runtime-dolphin"),
    "mupen64plus": ("local/emustack-mupen64plus:0.7.1", "runtime-mupen64plus"),
}


class PerProfileImageContracts(unittest.TestCase):
    def test_only_two_agent_profiles_use_dedicated_images(self):
        compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
        services = compose["services"]
        environments = json.loads((ROOT / "environments.json").read_text(encoding="utf-8"))["environments"]
        self.assertEqual(len(environments), 20)
        for env in environments:
            ident = env["id"]
            service = services[f"env-{ident}"]
            expected = PROFILE_TARGETS.get(ident, ("local/emustack:0.7.1", "runtime"))
            self.assertEqual((service["image"], service["build"]["target"]), expected, ident)
            self.assertNotIn("ports", service)
            self.assertNotIn("/var/run/docker.sock", str(service.get("volumes", [])))
        for ident in ("dashboard", "emustack"):
            self.assertEqual(services[ident]["image"], "local/emustack:0.7.1")
            self.assertEqual(services[ident]["build"]["target"], "runtime")
        self.assertEqual(services["dashboard-proxy"]["ports"], ["127.0.0.1:8765:8765"])

    def test_default_docker_build_still_uses_shared_runtime(self):
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertTrue(docker.rstrip().endswith("FROM runtime AS default"))
        self.assertIn("FROM runtime AS runtime-dolphin", docker)
        self.assertIn("FROM runtime AS runtime-mupen64plus", docker)
        self.assertIn("--exclude-dolphin", docker)
        self.assertIn("--only-profile dolphin", docker)
        self.assertIn("--only-profile mupen64plus", docker)

    def test_profile_only_updates_just_selected_installation_record(self):
        for profile, command in (("dolphin", "dolphin-emu"), ("mupen64plus", "mupen64plus-ui-console")):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                report = root / "report.json"
                target = root / "installed"
                init = subprocess.run(
                    [sys.executable, str(INSTALLER), "--skip-network", "--exclude-dolphin",
                     "--target", str(target), "--catalog", str(ROOT / "catalog.json"),
                     "--report", str(report)],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(init.returncode, 0, init.stdout + init.stderr)
                before = json.loads(report.read_text(encoding="utf-8"))["items"]
                self.assertEqual(before["dolphin"]["status"], "profile-image-only")
                bin_dir = root / "bin"
                bin_dir.mkdir()
                exe = bin_dir / command
                exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                exe.chmod(0o755)
                env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
                result = subprocess.run(
                    [sys.executable, str(INSTALLER), "--only-profile", profile,
                     "--skip-network", "--target", str(target),
                     "--catalog", str(ROOT / "catalog.json"), "--report", str(report)],
                    env=env, text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                after = json.loads(report.read_text(encoding="utf-8"))["items"]
                self.assertEqual(len(after), 20)
                self.assertEqual(after[profile]["status"], "installed")
                for other in before:
                    if other != profile:
                        self.assertEqual(before[other], after[other], other)

    def test_incomplete_base_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = root / "report.json"
            report.write_text('{"items":{}}', encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(INSTALLER), "--only-profile", "dolphin",
                 "--skip-network", "--target", str(root / "installed"),
                 "--catalog", str(ROOT / "catalog.json"), "--report", str(report)],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("incomplete", proc.stderr)
