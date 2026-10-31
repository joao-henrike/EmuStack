"""Source migration regression tests; no upstream clone or network is required."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "upstream" / "source-lock.json"
MANAGER = ROOT / "scripts" / "upstream-manager.py"


class UpstreamSourceManagementTests(unittest.TestCase):
    def test_all_20_profiles_and_24_official_source_modules_are_pinned(self):
        data = json.loads(LOCK.read_text(encoding="utf-8"))
        catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
        self.assertEqual({p["id"] for p in data["profiles"]},
                         {p["id"] for p in catalog["emulators"]})
        self.assertEqual(len(data["profiles"]), 20)
        self.assertEqual(len(data["sources"]), 24)
        self.assertEqual(len({s["id"] for s in data["sources"]}), 24)
        for s in data["sources"]:
            self.assertEqual(s["path"], f"third_party/{s['id']}")
            self.assertEqual(len(s["commit"]), 40)
            self.assertTrue(s["url"].startswith("https://"))
        self.assertEqual(len([s for s in data["sources"] if s["profile"] == "mupen64plus"]), 7)
        for id_ in ("xbox-one", "xbox-series"):
            profile = next(p for p in data["profiles"] if p["id"] == id_)
            self.assertEqual(profile["components"], [])
            self.assertEqual(profile["state"], "unsupported-no-source")

    def test_audit_checks_index_and_metadata_without_fetching_sources(self):
        result = subprocess.run(
            [sys.executable, str(MANAGER), "audit"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("20 profiles / 24 gitlinks", result.stdout)


if __name__ == "__main__":
    unittest.main()
