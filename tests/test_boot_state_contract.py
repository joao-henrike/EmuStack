import unittest
from unittest.mock import patch

import console_modes


class BootStateContractTests(unittest.TestCase):
    def test_prerequisites_enable_an_attempt_but_do_not_claim_a_boot(self):
        systems = {
            "schema_version": 1,
            "systems": [{
                "id": "ps1-bios-menu",
                "name": "PlayStation (PS1)",
                "interface_name": "BIOS",
                "family": "PlayStation",
                "emulator_ids": ["duckstation"],
                "boot_strategy": "duckstation-bios",
                "details": "Synthetic test profile.",
                "setup_steps": [],
            }],
        }
        catalog = {"emulators": [{"id": "duckstation", "name": "DuckStation"}]}
        checks = [{"label": "Synthetic BIOS fixture", "ok": True, "detail": "test only"}]

        with patch.object(console_modes, "detect_prerequisites", return_value=(True, checks, "/bios/test.rom")):
            resolved = console_modes.resolve_systems(
                catalog,
                lambda _item: ("AVAILABLE", "/opt/duckstation"),
                systems,
            )

        profile = resolved[0]
        self.assertTrue(profile["prerequisites_detected"])
        self.assertTrue(profile["can_attempt_boot"])
        self.assertTrue(profile["can_boot_original"])  # compatibility alias only
        self.assertFalse(profile["boot_observed"])
        self.assertFalse(profile["smoke_test_passed"])
        self.assertEqual(profile["boot_validation_status"], "attempt-available-not-tested")
        self.assertFalse(profile["runtime_boot_tested"])

    def test_unsupported_profile_cannot_be_attempted_even_if_a_launcher_exists(self):
        systems = {
            "schema_version": 1,
            "systems": [{
                "id": "ps5-system",
                "name": "PlayStation 5",
                "interface_name": "System UI",
                "family": "PlayStation",
                "emulator_ids": ["kytyps5"],
                "boot_strategy": "unsupported",
                "details": "Unsupported in this profile.",
                "setup_steps": [],
            }],
        }
        catalog = {"emulators": [{"id": "kytyps5", "name": "KytyPS5"}]}

        with patch.object(console_modes, "detect_prerequisites", return_value=(False, [], None)):
            resolved = console_modes.resolve_systems(
                catalog,
                lambda _item: ("AVAILABLE", "/opt/kytyps5"),
                systems,
            )

        profile = resolved[0]
        self.assertFalse(profile["can_attempt_boot"])
        self.assertFalse(profile["can_boot_original"])
        self.assertFalse(profile["boot_observed"])
        self.assertEqual(profile["boot_validation_status"], "not-ready")


if __name__ == "__main__":
    unittest.main(verbosity=2)
