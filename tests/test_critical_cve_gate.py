"""Regression tests for the fail-closed per-image CRITICAL CVE guard."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-critical-cves.py"
BASELINE = ROOT / "security-critical-baseline.json"


def module():
    spec = importlib.util.spec_from_file_location("check_critical_cves", SCRIPT)
    result = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(result)
    return result


def fixture(baseline):
    return {
        "schema_version": 1,
        "images": {
            name: {
                "image": item["image"],
                "critical_cve_ids": list(item["critical_ids"]),
                "unique_cves": {"CRITICAL": len(item["critical_ids"]), "HIGH": 0},
                "package_findings": {"CRITICAL": len(item["critical_ids"]), "HIGH": 0},
            }
            for name, item in baseline["images"].items()
        },
    }


class CriticalCveRegressionGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(BASELINE.read_text(encoding="utf-8"))
        cls.gate = module()

    def test_original_ci_249_inventory_is_accepted_but_explicitly_unresolved(self):
        matrix = fixture(self.policy)
        report, markdown, passed = self.gate.evaluate(matrix, self.policy)
        self.assertTrue(passed)
        self.assertTrue(report["pass"])
        self.assertIn("unresolved", markdown)
        self.assertNotIn("waiver accepted", markdown)
        self.assertEqual(len(report["images"]["mupen64plus"]["existing_unresolved"]), 6)

    def test_new_critical_fails_even_if_known_in_another_image(self):
        matrix = fixture(self.policy)
        name = "common"
        matrix["images"][name]["critical_cve_ids"].append("CVE-2025-48429")
        matrix["images"][name]["unique_cves"]["CRITICAL"] += 1
        matrix["images"][name]["package_findings"]["CRITICAL"] += 1
        report, markdown, passed = self.gate.evaluate(matrix, self.policy)
        self.assertFalse(passed)
        self.assertIn("CVE-2025-48429", report["images"][name]["new_critical"])
        self.assertIn("BLOCKED", markdown)

    def test_new_vulnerability_id_does_not_need_to_use_cve_namespace(self):
        matrix = fixture(self.policy)
        item = matrix["images"]["dolphin"]
        item["critical_cve_ids"].append("GHSA-abcd-efgh-1234")
        item["unique_cves"]["CRITICAL"] += 1
        item["package_findings"]["CRITICAL"] += 1
        self.assertFalse(self.gate.evaluate(matrix, self.policy)[2])

    def test_removed_vulnerability_is_reported_without_failing(self):
        matrix = fixture(self.policy)
        item = matrix["images"]["common"]
        item["critical_cve_ids"] = []
        item["unique_cves"]["CRITICAL"] = 0
        item["package_findings"]["CRITICAL"] = 0
        report, _, passed = self.gate.evaluate(matrix, self.policy)
        self.assertTrue(passed)
        self.assertEqual(report["images"]["common"]["no_longer_detected"], ["CVE-2026-6653"])

    def test_incomplete_or_unexpected_image_fails_closed(self):
        matrix = fixture(self.policy)
        del matrix["images"]["dolphin"]
        with self.assertRaisesRegex(ValueError, "three expected"):
            self.gate.evaluate(matrix, self.policy)
        matrix = fixture(self.policy)
        matrix["images"]["other"] = matrix["images"]["common"]
        with self.assertRaisesRegex(ValueError, "three expected"):
            self.gate.evaluate(matrix, self.policy)

    def test_mismatched_image_ref_and_inconsistent_counts_fail(self):
        matrix = fixture(self.policy)
        matrix["images"]["dolphin"]["image"] = "attacker/unknown:latest"
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.gate.evaluate(matrix, self.policy)
        matrix = fixture(self.policy)
        matrix["images"]["common"]["unique_cves"]["CRITICAL"] = 0
        with self.assertRaisesRegex(ValueError, "count"):
            self.gate.evaluate(matrix, self.policy)

    def test_baseline_must_not_silently_accept_untracked_critical_ids(self):
        matrix = fixture(self.policy)
        bad = json.loads(json.dumps(self.policy))
        del bad["tracked"]["CVE-2026-6653"]
        with self.assertRaisesRegex(ValueError, "individually tracked"):
            self.gate.evaluate(matrix, bad)
        bad = json.loads(json.dumps(self.policy))
        bad["policy"]["new_critical"] = "ignore"
        with self.assertRaisesRegex(ValueError, "must block"):
            self.gate.evaluate(matrix, bad)

    def test_duplicates_and_missing_identifiers_fail(self):
        matrix = fixture(self.policy)
        matrix["images"]["common"]["critical_cve_ids"].append("CVE-2026-6653")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.gate.evaluate(matrix, self.policy)
        matrix = fixture(self.policy)
        matrix["images"]["common"]["critical_cve_ids"] = ["UNKNOWN"]
        with self.assertRaisesRegex(ValueError, "invalid vulnerability"):
            self.gate.evaluate(matrix, self.policy)

    def test_ci_script_runs_gate_after_generating_matrix(self):
        shell = (ROOT / "scripts" / "supply-chain-matrix.sh").read_text(encoding="utf-8")
        self.assertIn("check-critical-cves.py", shell)
        self.assertIn("security-critical-baseline.json", shell)
        self.assertLess(shell.index("report-image-matrix.py"), shell.index("check-critical-cves.py"))
        self.assertIn("set -Eeuo pipefail", shell)
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("artifacts/critical-cve-gate-summary.md", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
