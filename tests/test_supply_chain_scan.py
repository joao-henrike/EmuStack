import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "supply-chain-tools.json"
SCRIPT_PATH = ROOT / "scripts" / "supply-chain-scan.sh"


class SupplyChainScanContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        cls.script = SCRIPT_PATH.read_text(encoding="utf-8")

    def test_tools_are_versioned_official_releases_with_pinned_hashes(self):
        tools = {item["id"]: item for item in self.lock["tools"]}
        self.assertEqual(set(tools), {"syft", "trivy"})
        expected_hosts = {
            "syft": "https://github.com/anchore/syft/releases/download/",
            "trivy": "https://github.com/aquasecurity/trivy/releases/download/",
        }
        for tool_id, tool in tools.items():
            self.assertRegex(tool["version"], r"^[0-9]+\.[0-9]+\.[0-9]+$")
            self.assertTrue(tool["url"].startswith(expected_hosts[tool_id]))
            self.assertIn(f"/v{tool['version']}/", tool["url"])
            self.assertRegex(tool["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(tool["executable"], tool_id)

    def test_scanner_policy_is_explicit_and_does_not_hide_unfixed_findings(self):
        policy = self.lock["scan_policy"]
        self.assertEqual(policy["mode"], "report-only")
        self.assertEqual(policy["severities"], ["HIGH", "CRITICAL"])
        self.assertEqual(policy["vulnerability_types"], ["os", "library"])
        self.assertEqual(policy["exit_code_on_findings"], 0)
        self.assertTrue(policy["fail_on_tool_download_checksum_or_scan_error"])
        self.assertIn("do not block", policy["rationale"].lower())
        self.assertIn("unfixed findings", policy["rationale"].lower())
        self.assertNotIn("--ignore-unfixed", self.script)
        self.assertIn("--exit-code 0", self.script)

    def test_script_resolves_repository_paths_and_uses_live_shell_expansions(self):
        self.assertIn("SCRIPT_DIR=\"$(cd -- \"$(dirname -- \"${BASH_SOURCE[0]}\")\" && pwd)\"", self.script)
        self.assertIn("ROOT=\"$(cd -- \"${SCRIPT_DIR}/..\" && pwd)\"", self.script)
        self.assertIn('LOCK_FILE="${ROOT}/supply-chain-tools.json"', self.script)
        self.assertNotIn(chr(92) + "${", self.script)
        self.assertLess(self.script.index('[[ -f "$LOCK_FILE" ]] ||'), self.script.index("IMAGE_REF="))

    def test_script_verifies_tool_hash_and_version_before_running_scanners(self):
        self.assertIn("set -Eeuo pipefail", self.script)
        self.assertIn("sha256sum --check", self.script)
        self.assertIn("version output does not match locked", self.script)
        self.assertIn("docker image inspect", self.script)
        self.assertIn("emustack-image.spdx.json", self.script)
        self.assertIn("emustack-trivy-vulnerabilities.json", self.script)
        self.assertIn("supply-chain-summary.md", self.script)
        self.assertIn("--scanners vuln", self.script)
        self.assertIn("--vuln-type os,library", self.script)
        self.assertIn("--severity HIGH,CRITICAL", self.script)

    def test_image_reference_matches_the_compose_dashboard_image(self):
        policy_image = self.lock["target_image"]
        self.assertTrue(policy_image)
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        dashboard = compose.split("  dashboard:\n", 1)[1]
        image_line = next(line.strip().split(":", 1)[1].strip() for line in dashboard.splitlines() if line.strip().startswith("image:"))
        self.assertEqual(policy_image, image_line)
        self.assertEqual(re.findall(r"local/emustack:[0-9]+\.[0-9]+\.[0-9]+", image_line), [image_line])


if __name__ == "__main__":
    unittest.main(verbosity=2)
