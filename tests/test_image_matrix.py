"""Fixture-backed tests for independent per-image Trivy/Syft reporting."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "report-image-matrix.py"


def load_reporter():
    spec = importlib.util.spec_from_file_location("report_image_matrix", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_fixtures(root: Path):
    examples = {
        "common": [("CVE-COMMON", "HIGH")],
        "dolphin": [("CVE-COMMON", "HIGH"), ("CVE-DOLPHIN", "CRITICAL"), ("CVE-DOLPHIN", "CRITICAL")],
        "mupen64plus": [("CVE-COMMON", "HIGH"), ("CVE-MUPEN", "CRITICAL")],
    }
    for name, records in examples.items():
        folder = root / name
        folder.mkdir()
        (folder / "emustack-trivy-vulnerabilities.json").write_text(json.dumps({
            "Results": [{"Target": "debian", "Vulnerabilities": [
                {"VulnerabilityID": cve, "Severity": severity, "PkgName": name}
                for cve, severity in records
            ]}],
        }), encoding="utf-8")
        (folder / "emustack-image.spdx.json").write_text(
            json.dumps({"packages": [{"name": name}]}), encoding="utf-8")
        (folder / "supply-chain-summary.md").write_text("# scan\n", encoding="utf-8")


class PerImageMatrixTests(unittest.TestCase):
    def test_three_distinct_scans_and_deduplication(self):
        reporter = load_reporter()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_fixtures(root)
            matrix, markdown = reporter.build_matrix(root)
            self.assertEqual(set(matrix["images"]), {"common", "dolphin", "mupen64plus"})
            self.assertEqual(matrix["images"]["dolphin"]["package_findings"]["CRITICAL"], 2)
            self.assertEqual(matrix["images"]["dolphin"]["unique_cves"]["CRITICAL"], 1)
            self.assertEqual(matrix["images"]["common"]["unique_cves"]["HIGH"], 1)
            self.assertEqual(matrix["additional_cve_ids_vs_common"]["dolphin"], ["CVE-DOLPHIN"])
            self.assertEqual(matrix["additional_cve_ids_vs_common"]["mupen64plus"], ["CVE-MUPEN"])
            self.assertIn("### dolphin", markdown)
            self.assertIn("not proof of exploitability", markdown)

    def test_missing_or_invalid_report_fails_closed(self):
        reporter = load_reporter()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(ValueError):
                reporter.build_matrix(root)
            write_fixtures(root)
            (root / "dolphin" / "emustack-trivy-vulnerabilities.json").write_text(
                '{"Results": null}', encoding="utf-8")
            with self.assertRaises(ValueError):
                reporter.build_matrix(root)


if __name__ == "__main__":
    unittest.main()
