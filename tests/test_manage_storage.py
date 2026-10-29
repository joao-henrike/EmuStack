import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("manage_storage", ROOT / "scripts/manage-storage.py")
manage_storage = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(manage_storage)


class ManageStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.data_root = self.base / "data" / "environments"
        self.backup_root = self.base / "backups"
        self.staging_root = self.base / "restore-staging"
        self.patches = [
            patch.object(manage_storage, "DATA_ROOT", self.data_root),
            patch.object(manage_storage, "BACKUP_ROOT", self.backup_root),
            patch.object(manage_storage, "STAGING_ROOT", self.staging_root),
        ]
        for item in self.patches: item.start()

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()

    def test_init_and_inspect_create_separate_environment_layout(self):
        layout = manage_storage.ensure_layout("rpcs3")
        self.assertEqual(set(layout), set(manage_storage.ALLOWED_DIRS))
        report = manage_storage.inspect_env("rpcs3")
        self.assertEqual(report["environment_id"], "rpcs3")
        self.assertEqual(report["total_files"], 0)
        with self.assertRaises(ValueError): manage_storage.validate_env("../rpcs3")

    def test_shared_environment_parent_symlink_is_refused(self):
        outer = self.base / "actual-data"
        target = outer / "environments"
        target.mkdir(parents=True)
        alias_parent = self.base / "alias-data"
        alias_parent.symlink_to(outer, target_is_directory=True)
        alias = alias_parent / "environments"
        with patch.object(manage_storage, "DATA_ROOT", alias):
            with self.assertRaisesRegex(ValueError, "shared data root"):
                manage_storage.env_root("rpcs3")

    def test_environment_root_symlink_cannot_alias_another_console(self):
        self.data_root.mkdir(parents=True)
        real = self.data_root / "rpcs3"
        real.mkdir()
        (real / "home").mkdir()
        (self.data_root / "xemu").symlink_to(real, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink environment root"):
            manage_storage.env_root("xemu")
        with self.assertRaisesRegex(ValueError, "symlink environment root"):
            manage_storage.ensure_layout("xemu")

    def test_backup_restore_round_trip_checks_hashes_and_keeps_rollback(self):
        root = manage_storage.env_root("rpcs3")
        (root / "home").mkdir(parents=True)
        (root / "home" / "state.json").write_text('{"version":1}', encoding="utf-8")
        archive = manage_storage.backup_env("rpcs3", self.base / "snapshot.tar.gz", allow_running=True)
        self.assertTrue(archive.is_file())
        (root / "home" / "state.json").write_text('{"version":2}', encoding="utf-8")
        rollback = manage_storage.restore_env("rpcs3", archive, allow_running=True)
        self.assertEqual((manage_storage.env_root("rpcs3") / "home" / "state.json").read_text(), '{"version":1}')
        self.assertTrue(rollback.exists(), "old environment remains available as rollback")
        with manage_storage.tarfile.open(archive, "r:gz") as tar:
            manifest = json.load(tar.extractfile("manifest.json"))
        self.assertEqual(manifest["environment_id"], "rpcs3")
        self.assertEqual(manifest["file_count"], 1)

    def test_restore_refuses_snapshot_from_another_environment(self):
        root = manage_storage.env_root("rpcs3")
        root.mkdir(parents=True)
        (root / "home").mkdir()
        (root / "home" / "x").write_text("fixture", encoding="utf-8")
        archive = manage_storage.backup_env("rpcs3", self.base / "snapshot.tar.gz", allow_running=True)
        with self.assertRaisesRegex(ValueError, "different environment"):
            manage_storage.restore_env("xemu", archive, allow_running=True)

    def test_backup_refuses_symlinks(self):
        root = manage_storage.env_root("xemu")
        root.mkdir(parents=True)
        (root / "home").mkdir()
        (root / "home" / "outside-link").symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlinks are not allowed"):
            manage_storage.backup_env("xemu", self.base / "bad.tar.gz", allow_running=True)


    def test_truncated_snapshot_is_rejected_without_changing_environment(self):
        root = manage_storage.env_root("rpcs3")
        (root / "home").mkdir(parents=True)
        state_file = root / "home" / "state.json"
        state_file.write_text("current-state", encoding="utf-8")
        archive = manage_storage.backup_env("rpcs3", self.base / "snapshot.tar.gz", allow_running=True)
        state_file.write_text("still-current", encoding="utf-8")
        raw = archive.read_bytes()
        archive.write_bytes(raw[: max(1, len(raw) // 2)])

        with self.assertRaisesRegex(ValueError, "corrupt or truncated"):
            manage_storage.restore_env("rpcs3", archive, allow_running=True)

        self.assertEqual(state_file.read_text(encoding="utf-8"), "still-current")
        self.assertEqual(list(self.staging_root.glob("restore-*")), [])

    def test_manifest_metadata_mismatch_is_rejected_without_replacing_environment(self):
        root = manage_storage.env_root("rpcs3")
        (root / "home").mkdir(parents=True)
        state_file = root / "home" / "state.json"
        state_file.write_text("current-state", encoding="utf-8")
        archive = manage_storage.backup_env("rpcs3", self.base / "snapshot.tar.gz", allow_running=True)
        state_file.write_text("still-current", encoding="utf-8")
        tampered = self.base / "bad-manifest.tar.gz"

        with manage_storage.tarfile.open(archive, "r:gz") as source, manage_storage.tarfile.open(tampered, "w:gz") as destination:
            for member in source.getmembers():
                if member.name == "manifest.json":
                    extracted = source.extractfile(member)
                    self.assertIsNotNone(extracted)
                    manifest = json.loads(extracted.read().decode("utf-8"))
                    manifest["file_count"] += 1
                    payload = json.dumps(manifest).encode("utf-8")
                    info = manage_storage._tar_info("manifest.json", len(payload))
                    destination.addfile(info, io.BytesIO(payload))
                else:
                    fileobj = source.extractfile(member) if member.isfile() else None
                    destination.addfile(member, fileobj)

        with self.assertRaisesRegex(ValueError, "file_count"):
            manage_storage.restore_env("rpcs3", tampered, allow_running=True)

        self.assertEqual(state_file.read_text(encoding="utf-8"), "still-current")
        self.assertEqual(list(self.staging_root.glob("restore-*")), [])

    def test_payload_hash_mismatch_is_rejected_without_replacing_environment(self):
        root = manage_storage.env_root("rpcs3")
        (root / "home").mkdir(parents=True)
        state_file = root / "home" / "state.json"
        state_file.write_text("state-v1", encoding="utf-8")
        archive = manage_storage.backup_env("rpcs3", self.base / "snapshot.tar.gz", allow_running=True)
        state_file.write_text("still-current", encoding="utf-8")
        tampered = self.base / "bad-payload.tar.gz"

        with manage_storage.tarfile.open(archive, "r:gz") as source, manage_storage.tarfile.open(tampered, "w:gz") as destination:
            for member in source.getmembers():
                if member.isfile():
                    fileobj = source.extractfile(member)
                    self.assertIsNotNone(fileobj)
                    payload = fileobj.read()
                    if member.name == "environment/rpcs3/home/state.json":
                        payload = b"state-v2"
                        member.size = len(payload)
                        destination.addfile(member, io.BytesIO(payload))
                    else:
                        destination.addfile(member, io.BytesIO(payload))
                else:
                    destination.addfile(member)

        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            manage_storage.restore_env("rpcs3", tampered, allow_running=True)

        self.assertEqual(state_file.read_text(encoding="utf-8"), "still-current")
        self.assertEqual(list(self.staging_root.glob("restore-*")), [])

    def test_non_object_snapshot_manifest_is_reported_as_invalid(self):
        archive = self.base / "invalid-manifest.tar.gz"
        payload = b"[]"
        with manage_storage.tarfile.open(archive, "w:gz") as destination:
            destination.addfile(manage_storage._tar_info("manifest.json", len(payload)), io.BytesIO(payload))

        with self.assertRaisesRegex(ValueError, "manifest must be a JSON object"):
            manage_storage.restore_env("rpcs3", archive, allow_running=True)

        self.assertEqual(list(self.staging_root.glob("restore-*")), [])


if __name__ == "__main__": unittest.main(verbosity=2)
