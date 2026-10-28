import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import console_modes


class ConsoleSystemProfilesTests(unittest.TestCase):
    def test_profiles_are_unique_and_have_documented_strategies(self):
        payload = console_modes.load_systems()
        systems = payload["systems"]
        ids = [item["id"] for item in systems]
        self.assertGreaterEqual(len(systems), 18)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(item.get("official_docs") for item in systems))

    def test_resolver_does_not_claim_ps5_full_system_boot(self):
        payload = console_modes.load_systems()
        catalog = {"emulators": [{"id": "kytyps5", "name": "KytyPS5"}]}
        resolved = console_modes.resolve_systems(catalog, lambda item: ("AVAILABLE", "/usr/bin/kytyps5"), payload)
        ps5 = next(item for item in resolved if item["id"] == "ps5-system")
        self.assertEqual(ps5["state"], "unsupported")
        self.assertFalse(ps5["can_boot_original"])

    def test_pcsx2_uses_current_bios_boot_flag_and_requires_user_bios(self):
        payload = console_modes.load_systems()
        profile = next(item for item in payload["systems"] if item["id"] == "ps2-bios-menu")
        with tempfile.TemporaryDirectory() as tmp:
            bios_dir = Path(tmp) / "pcsx2"
            bios_dir.mkdir()
            (bios_dir / "bios.bin").write_bytes(b"fixture only, not a real BIOS")
            with patch.object(console_modes, "BIOS_DIR", Path(tmp)):
                cmd = console_modes.build_boot_command("ps2-bios-menu", "/usr/bin/pcsx2", payload)
        self.assertEqual(cmd, ["/usr/bin/pcsx2", "-bios", "-fullscreen"])

    def test_xemu_configuration_is_reported_as_unverified_not_authentic_verified(self):
        payload = console_modes.load_systems()
        catalog = {"emulators": [{"id": "xemu", "name": "xemu"}]}
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "xemu.toml"
            config.write_text("# test config only\n", encoding="utf-8")
            with patch.object(console_modes, "XEMU_CONFIG", config):
                resolved = console_modes.resolve_systems(catalog, lambda item: ("AVAILABLE", "/usr/bin/xemu"), payload)
        xbox = next(item for item in resolved if item["id"] == "xbox-original-dashboard")
        self.assertEqual(xbox["state"], "needs-setup")
        self.assertIn("Configure MCPX", xbox["state_label"])
        self.assertFalse(xbox["can_boot_original"], "config alone cannot authenticate the original Xbox dashboard")
        self.assertTrue(xbox["can_open_emulator"])

    def test_duckstation_bios_boot_requires_user_bios_and_uses_fullscreen_cli(self):
        payload = console_modes.load_systems()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bios = base / "bios"
            bios.mkdir()
            (bios / "scph5501.bin").write_bytes(b"test fixture, not a BIOS")
            with patch.object(console_modes, "BIOS_DIR", bios):
                resolved = console_modes.resolve_systems(
                    {"emulators": [{"id": "duckstation", "name": "DuckStation"}]},
                    lambda _item: ("AVAILABLE", "/opt/DuckStation-x64.AppImage"), payload)
                ps1 = next(item for item in resolved if item["id"] == "ps1-bios-menu")
                self.assertTrue(ps1["can_boot_original"])
                self.assertFalse(ps1["runtime_boot_tested"])
                cmd = console_modes.build_boot_command("ps1-bios-menu", "/opt/DuckStation-x64.AppImage", payload)
        self.assertEqual(cmd, ["/opt/DuckStation-x64.AppImage", "-bios", "-fullscreen"])

    def test_xemu_attestation_is_bound_to_hash_and_configured_container_path(self):
        payload = console_modes.load_systems()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home, bios, saves = base / "home", base / "bios", base / "saves"
            (home / ".config/xemu").mkdir(parents=True)
            bios.mkdir(); saves.mkdir()
            bootrom = bios / "mcpx.bin"; bootrom.write_bytes(b"fixture-mcpx")
            flashrom = bios / "flash.bin"; flashrom.write_bytes(b"fixture-bios")
            hdd = saves / "xbox-hdd.qcow2"; hdd.write_bytes(b"fixture-hdd")
            config = home / ".config/xemu/xemu.toml"
            config.write_text(
                f'[files]\nbootrom_path = "{bootrom}"\nflashrom_path = "{flashrom}"\nhdd_path = "{hdd}"\n',
                encoding="utf-8")
            import hashlib
            attestation = bios / "xemu-dashboard-attestation.json"
            attestation.write_text(json.dumps({
                "schema_version": 1, "environment_id": "xemu", "dashboard_type": "microsoft-retail",
                "user_confirmed": True, "hdd_sha256": hashlib.sha256(hdd.read_bytes()).hexdigest(),
                "hdd_container_path": "/saves/xbox-hdd.qcow2",
            }), encoding="utf-8")
            with patch.object(console_modes, "HOME", home), patch.object(console_modes, "BIOS_DIR", bios), \
                 patch.object(console_modes, "SAVES_DIR", saves), patch.object(console_modes, "XEMU_CONFIG", config), \
                 patch.object(console_modes, "XEMU_ATTESTATION", attestation):
                ready, checks, _ = console_modes.detect_prerequisites(next(x for x in payload["systems"] if x["id"] == "xbox-original-dashboard"))
                self.assertTrue(ready, checks)
                cmd = console_modes.build_boot_command("xbox-original-dashboard", "/usr/bin/xemu", payload)
                # The same hash at another path is not accepted: path binding prevents accidental reuse.
                att = json.loads(attestation.read_text())
                att["hdd_container_path"] = "/home/emu/moved.qcow2"
                attestation.write_text(json.dumps(att), encoding="utf-8")
                ready_after_path_tamper, _, _ = console_modes.detect_prerequisites(next(x for x in payload["systems"] if x["id"] == "xbox-original-dashboard"))
                self.assertFalse(ready_after_path_tamper)
        self.assertEqual(cmd, ["/usr/bin/xemu", "-full-screen", "-config_path", str(config)])


    def test_ppsspp_vsh_requires_realistic_flash0_tree_and_builds_experimental_command(self):
        payload = console_modes.load_systems()
        profile = next(item for item in payload["systems"] if item["id"] == "psp-system")
        self.assertEqual(profile["boot_strategy"], "ppsspp-vsh")
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            flash0 = assets / "flash0"
            (flash0 / "vsh/module").mkdir(parents=True)
            (flash0 / "kd").mkdir(parents=True)
            (flash0 / "vsh/module/vshmain.prx").write_bytes(b"fixture-not-real-firmware")
            (flash0 / "kd/pspbtcnf.bin").write_bytes(b"fixture-not-real-firmware")
            with patch.object(console_modes, "PPSSPP_ASSET_DIR", assets):
                ready, checks, target = console_modes.detect_prerequisites(profile)
                self.assertTrue(ready, checks)
                self.assertEqual(target, str(flash0))
                command = console_modes.build_boot_command("psp-system", "/opt/ppsspp", payload)
            self.assertEqual(command, ["/opt/ppsspp", "--vsh", "--fullscreen"])
            (flash0 / "vsh/module/vshmain.prx").unlink()
            with patch.object(console_modes, "PPSSPP_ASSET_DIR", assets):
                ready_after_missing_file, _, _ = console_modes.detect_prerequisites(profile)
                self.assertFalse(ready_after_missing_file)

    def test_dolphin_wii_menu_boot_keeps_graphical_interface_visible(self):
        payload = console_modes.load_systems()
        profile = next(item for item in payload["systems"] if item["id"] == "wii-menu")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            menu_dir = home / ".local/share/dolphin-emu/Wii/title/00000001/00000002"
            menu_dir.mkdir(parents=True)
            with patch.object(console_modes, "HOME", home):
                command = console_modes.build_boot_command("wii-menu", "/usr/bin/dolphin-emu", payload)
        self.assertEqual(command, ["/usr/bin/dolphin-emu", "--nand_title=0000000100000002"])
        self.assertNotIn("-b", command, "-b is batch mode and suppresses the GUI needed to see the system menu")

    def test_unsupported_system_cannot_produce_boot_command(self):
        with self.assertRaises(ValueError):
            console_modes.build_boot_command("ps5-system", "/usr/bin/ps5", console_modes.load_systems())


if __name__ == "__main__":
    unittest.main(verbosity=2)
