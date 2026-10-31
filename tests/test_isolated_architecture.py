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
        dashboard_service = compose.split("  dashboard:", 1)[1].split("\n  dashboard-proxy:", 1)[0]
        proxy_service = compose.split("  dashboard-proxy:", 1)[1].split("\nnetworks:", 1)[0]
        self.assertNotIn('127.0.0.1:8765:8765', dashboard_service)
        self.assertIn('127.0.0.1:8765:8765', proxy_service)
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
            self.assertRegex(block, rf"(?m)^    networks:\n      env-{re.escape(env_id)}-net:\n        ipv4_address: 172\.28\.\d+\.2$")
            token_suffix = env_id.upper().replace("-", "_")
            self.assertIn(f"EMUSTACK_AGENT_TOKEN: ${{EMUSTACK_AGENT_TOKEN_{token_suffix}:-}}", block)
            self.assertIn('entrypoint: ["python3", "/opt/emustack/console_agent.py"]', block)
            network_match = re.search(rf"(?ms)^  env-{re.escape(env_id)}-net:\n(.*?)(?=^  [^\s].*:\n|\Z)", compose)
            self.assertIsNotNone(network_match, env_id)
            self.assertIn("internal: true", network_match.group(1))

    def test_dashboard_mutation_boundary_uses_gateway_allowlist_and_unique_static_ips(self):
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        dashboard_block = compose.split("  dashboard:", 1)[1].split("    depends_on:", 1)[0]
        self.assertIn("EMUSTACK_CONTROL_TRUSTED_CLIENT_IPS:", dashboard_block)
        self.assertNotIn("./data/environments", dashboard_block)
        manifest = json.loads((ROOT / "environments.json").read_text(encoding="utf-8"))
        ids = [record["id"] for record in manifest["environments"]]
        self.assertEqual(len(ids), 20)
        for index, env_id in enumerate(ids, 1):
            subnet = f"172.28.{index}.0/24"
            gateway = f"172.28.{index}.1"
            agent_ip = f"172.28.{index}.2"
            dashboard_ip = f"172.28.{index}.3"
            network_block = re.search(rf"(?ms)^  env-{re.escape(env_id)}-net:\n(.*?)(?=^  [^\s].*:\n|\Z)", compose).group(1)
            self.assertIn(f"subnet: {subnet}", network_block, env_id)
            self.assertIn(f"gateway: {gateway}", network_block, env_id)
            service_block = re.search(rf"(?ms)^  env-{re.escape(env_id)}:\n(.*?)(?=^  [^\s].*:\n|\Z)", compose).group(1)
            self.assertIn(f"ipv4_address: {agent_ip}", service_block, env_id)
            self.assertIn(f"ipv4_address: {dashboard_ip}", dashboard_block, env_id)
            self.assertIn(gateway, dashboard_block, env_id)
        webapp = (ROOT / "webapp.py").read_text(encoding="utf-8")
        self.assertIn("_is_trusted_dashboard_client(self.client_address[0])", webapp)
        self.assertIn("ipaddress.ip_address", webapp)

    def test_dashboard_loopback_proxy_preserves_internal_dashboard_boundary(self):
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        dashboard = compose.split("  dashboard:", 1)[1].split("\n  dashboard-proxy:", 1)[0]
        proxy = compose.split("  dashboard-proxy:", 1)[1].split("\nnetworks:", 1)[0]
        self.assertNotIn('127.0.0.1:8765:8765', dashboard)
        self.assertNotIn("dashboard-proxy-edge", dashboard)
        self.assertIn("dashboard-proxy-backend:", dashboard)
        self.assertIn("ipv4_address: 172.29.0.3", dashboard)
        self.assertIn('image: nginx:alpine@sha256:785835ea65db4bba6f021acc0f3be91b0fef76a53fe41f8588c6698d2aed0606', proxy)
        self.assertIn('127.0.0.1:8765:8765', proxy)
        self.assertIn("ipv4_address: 172.29.0.2", proxy)
        self.assertIn("./proxy/nginx.conf:/etc/nginx/nginx.conf:ro", proxy)
        self.assertIn('user: "101:101"', proxy)
        self.assertIn("no-new-privileges:true", proxy)
        self.assertIn("cap_drop: [ALL]", proxy)

        networks = compose.split("\nnetworks:\n", 1)[1]
        backend = re.search(r"(?ms)^  dashboard-proxy-backend:\n(.*?)(?=^  [^\s].*:\n|\Z)", networks)
        edge = re.search(r"(?ms)^  dashboard-proxy-edge:\n(.*?)(?=^  [^\s].*:\n|\Z)", networks)
        self.assertIsNotNone(backend)
        self.assertIsNotNone(edge)
        self.assertIn("internal: true", backend.group(1))
        self.assertNotIn("internal: true", edge.group(1))

        nginx = (ROOT / "proxy" / "nginx.conf").read_text(encoding="utf-8")
        self.assertIn("proxy_pass http://dashboard:8765;", nginx)
        self.assertIn("proxy_set_header Host $http_host;", nginx)
        self.assertIn("proxy_set_header Origin $http_origin;", nginx)
        self.assertIn("proxy_set_header X-EmuStack-Request $http_x_emustack_request;", nginx)
        self.assertNotIn("X-Forwarded-For", nginx)
        for directive in (
            "client_body_temp_path",
            "proxy_temp_path",
            "fastcgi_temp_path",
            "uwsgi_temp_path",
            "scgi_temp_path",
        ):
            self.assertRegex(nginx, rf"(?m)^{directive} /tmp/[a-z_]+;$")

    def test_dashboard_proxy_source_is_allowlisted_without_trusting_agents(self):
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        dashboard = compose.split("  dashboard:", 1)[1].split("\n  dashboard-proxy:", 1)[0]
        self.assertIn("172.29.0.2", dashboard)
        for index in range(1, 21):
            self.assertIn(f"172.28.{index}.1", dashboard)
            self.assertNotIn(f"172.28.{index}.2", dashboard)

    def test_dashboard_startup_does_not_wait_for_all_agents_to_be_healthy(self):
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        dashboard_block = compose.split("  dashboard:", 1)[1]
        dependency_block = dashboard_block.split("    depends_on:", 1)[1].split("    command:", 1)[0]
        self.assertEqual(dependency_block.count("condition: service_started"), len(EXPECTED_IDS))
        self.assertNotIn("condition: service_healthy", dependency_block)

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
