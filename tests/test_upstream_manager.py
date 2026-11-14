"""Source migration regression tests; no upstream clone or network is required."""
import json
import importlib.util
import tempfile
from unittest.mock import patch
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

    def test_official_source_allowlist_rejects_impostor_repository(self):
        spec = importlib.util.spec_from_file_location("emustack_upstream_manager", MANAGER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        payload = json.loads(LOCK.read_text(encoding="utf-8"))
        payload["sources"][0]["url"] = "https://github.com/untrusted/fake-emulator.git"
        with tempfile.TemporaryDirectory() as td:
            changed_lock = Path(td) / "source-lock.json"
            changed_lock.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(module, "LOCK", changed_lock):
                with self.assertRaisesRegex(ValueError, "changed official origin"):
                    module.validate()

    def test_gitlinks_are_pinned_to_source_manifest(self):
        spec = importlib.util.spec_from_file_location("emustack_upstream_manager", MANAGER)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        _, sources = module.validate()
        module.check_index(sources)
        corrupted = [dict(s) for s in sources]
        corrupted[0]["commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "Git index gitlink mismatch"):
            module.check_index(corrupted)

    def test_audit_checks_index_and_metadata_without_fetching_sources(self):
        result = subprocess.run(
            [sys.executable, str(MANAGER), "audit"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("20 profiles / 24 gitlinks", result.stdout)


if __name__ == "__main__":
    unittest.main()
