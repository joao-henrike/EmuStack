import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IDS = {
    "kytyps5", "shadps4", "rpcs3", "duckstation", "pcsx2", "ppsspp", "vita3k",
    "xbox-one", "xenia-canary", "xbox-series", "xemu", "eden", "cemu", "dolphin",
    "azahar", "melonds", "mgba", "mupen64plus", "bsnes", "mesen",
}


class IsolatedArchitectureTests(unittest.TestCase):
    def test_manifest_has_twenty_unique_environment_roots(self):
        payload = json.loads((ROOT / "environments.json").read_text(encoding="utf-8"))
        records = payload["environments"]
        self.assertEqual({record["id"] for record in records}, EXPECTED_IDS)
        self.assertEqual(len(records), 20)
        roots = [record["directories"]["root"] for record in records]
        self.assertEqual(len(roots), len(set(roots)))
        for record in records:
            root = record["directories"]["root"]
            for key in ("games", "bios", "saves", "config_home", "custom_emulators"):
                self.assertTrue(record["directories"][key].startswith(root + "/"), (record["id"], key))
            self.assertEqual(record["isolation"]["cross_environment_storage"], "denied by default")

    def test_each_agent_has_unique_mounts_and_private_internal_network(self):
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertNotIn("/var/run/docker.sock", compose)
        self.assertIn('EMUSTACK_ISOLATED_MODE: "1"', compose)
        dashboard_block = compose.split("  dashboard:", 1)[1].split("\nnetworks:", 1)[0]
        for env_id in EXPECTED_IDS:
            token_suffix = env_id.upper().replace("-", "_")
            self.assertIn(f"EMUSTACK_AGENT_TOKEN_{token_suffix}: ${{EMUSTACK_AGENT_TOKEN_{token_suffix}:-}}", dashboard_block)
        self.assertIn('127.0.0.1:8765:8765', compose)
        self.assertNotIn("./data/environments", compose.split("  dashboard:", 1)[1].split("\nnetworks:", 1)[0])
        for env_id in EXPECTED_IDS:
            block_match = re.search(rf"(?ms)^  env-{re.escape(env_id)}:\n(.*?)(?=^  [a-zA-Z0-9_-]+:\n|^networks:\n)", compose)
            self.assertIsNotNone(block_match, env_id)
            block = block_match.group(1)
            self.assertIn(f"./data/environments/{env_id}/games:/games:ro", block)
            self.assertIn(f"./data/environments/{env_id}/bios:/bios:ro", block)
            self.assertIn(f"./data/environments/{env_id}/saves:/saves:rw", block)
            self.assertIn(f"./data/environments/{env_id}/home:/home/emu:rw", block)
            self.assertIn(f"./data/environments/{env_id}/emulators:/custom-emulators:ro", block)
            self.assertIn(f"networks: [env-{env_id}-net]", block)
            token_suffix = env_id.upper().replace("-", "_")
            self.assertIn(f"EMUSTACK_AGENT_TOKEN: ${{EMUSTACK_AGENT_TOKEN_{token_suffix}:-}}", block)
            self.assertIn('entrypoint: ["python3", "/opt/emustack/console_agent.py"]', block)
            self.assertIn("internal: true", compose.split(f"  env-{env_id}-net:", 1)[1].split("\n  env-", 1)[0])

    def test_xemu_dashboard_is_not_advertised_as_verified_original_boot(self):
        payload = json.loads((ROOT / "environments.json").read_text(encoding="utf-8"))
        xemu = next(item for item in payload["environments"] if item["id"] == "xemu")
        self.assertEqual(xemu["capability_level"], "MANUAL_SYSTEM_BOOT")
        self.assertIn("não é autenticado automaticamente", xemu["capability_note"])

    def test_capability_manifest_does_not_claim_full_dashboards_for_experimental_consoles(self):
        payload = json.loads((ROOT / "environments.json").read_text(encoding="utf-8"))
        by_id = {record["id"]: record for record in payload["environments"]}
        for env_id in ("kytyps5", "shadps4", "xenia-canary", "eden", "vita3k", "ppsspp"):
            level = by_id[env_id]["capability_level"]
            self.assertNotIn("DASHBOARD_BOOT", level, env_id)
            self.assertNotIn("FULL_SYSTEM", level, env_id)

    def test_base_image_digest_is_pinned_and_apt_snapshot_is_explicit_opt_in(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("debian:trixie-slim@sha256:89c1ea91e897f0fe0a3731595330bc45b8bdef4047464a07116f891a94054b31", dockerfile)
        self.assertIn("APT_SNAPSHOT_TIMESTAMP", dockerfile)
        self.assertIn("APT_SNAPSHOT_TIMESTAMP: ${APT_SNAPSHOT_TIMESTAMP:-}", compose)
        self.assertIn("snapshot.debian.org/archive/debian-security", dockerfile)

    def test_unavailable_xbox_generations_have_no_fake_launchers(self):
        catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
        by_id = {item["id"]: item for item in catalog["emulators"]}
        for env_id in ("xbox-one", "xbox-series"):
            self.assertEqual(by_id[env_id]["runtime"], "unsupported")
            self.assertEqual(by_id[env_id]["commands"], [])
            self.assertEqual(by_id[env_id]["game_arg"], "blocked")

    def test_ps1_ppsspp_and_vita_profiles_are_real_distinct_platform_profiles(self):
        catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
        by_id = {item["id"]: item for item in catalog["emulators"]}
        self.assertEqual(by_id["duckstation"]["platform"], "PlayStation 1")
        self.assertEqual(by_id["ppsspp"]["platform"], "PlayStation Portable (PSP)")
        self.assertEqual(by_id["vita3k"]["platform"], "PlayStation Vita")
        systems = json.loads((ROOT / "console-systems.json").read_text(encoding="utf-8"))["systems"]
        by_system = {item["id"]: item for item in systems}
        self.assertEqual(by_system["ps1-bios-menu"]["boot_strategy"], "duckstation-bios")
        self.assertEqual(by_system["psp-system"]["boot_strategy"], "ppsspp-vsh")
        self.assertEqual(by_system["psvita-system"]["boot_strategy"], "unsupported")


if __name__ == "__main__":
    unittest.main(verbosity=2)
