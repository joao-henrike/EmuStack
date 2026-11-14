import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase1-builder" / "apt-security-bootstrap.sh"


class AptSecurityBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.runtime_dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        cls.builder_dockerfile = (ROOT / "scripts" / "phase1-builder" / "Dockerfile").read_text(encoding="utf-8")

    def test_initial_apt_operations_disable_retries_before_fixed_version(self):
        self.assertIn("apt-get -o Acquire::Retries=0 update", self.script)
        self.assertIn("apt-get -o Acquire::Retries=0 install -y --no-install-recommends apt", self.script)

    def test_bootstrap_requires_and_verifies_fixed_apt_version(self):
        self.assertIn('MIN_APT_VERSION="3.0.4"', self.script)
        self.assertIn('dpkg --compare-versions "$candidate" ge "$MIN_APT_VERSION"', self.script)
        self.assertIn('dpkg --compare-versions "$installed" ge "$MIN_APT_VERSION"', self.script)

    def test_bootstrap_upgrades_installed_security_packages(self):
        self.assertIn("apt-get upgrade -y --no-install-recommends", self.script)

    def test_both_runtime_and_phase1_builder_execute_the_same_bootstrap(self):
        self.assertIn("apt-security-bootstrap.sh /tmp/apt-security-bootstrap.sh", self.runtime_dockerfile)
        self.assertIn("sh /tmp/apt-security-bootstrap.sh", self.runtime_dockerfile)
        self.assertIn("COPY apt-security-bootstrap.sh /tmp/apt-security-bootstrap.sh", self.builder_dockerfile)
        self.assertIn("sh /tmp/apt-security-bootstrap.sh", self.builder_dockerfile)


if __name__ == "__main__":
    unittest.main(verbosity=2)
