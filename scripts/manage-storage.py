#!/usr/bin/env python3
"""Safely inspect, back up, restore, and create neutral data disks for EmuStack.

This does not install console firmware or turn a blank disk into a bootable console.
Restores are transactional: the current environment root is moved into a rollback
folder before the verified snapshot is promoted.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "environments.json"
DATA_ROOT = ROOT / "data" / "environments"
BACKUP_ROOT = ROOT / "backups"
STAGING_ROOT = ROOT / "data" / "restore-staging"
VERSION = "0.7.1"
ALLOWED_DIRS = ("games", "bios", "saves", "home", "emulators")
MAX_BACKUP_BYTES = 2 * 1024**4  # 2 TiB uncompressed upper bound


def environment_ids() -> set[str]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ids = {str(item["id"]) for item in data.get("environments", [])}
    if len(ids) != len(data.get("environments", [])) or not ids:
        raise RuntimeError("environments.json contains missing/duplicate IDs")
    return ids


def validate_env(raw: str) -> str:
    if raw not in environment_ids():
        raise ValueError(f"Unknown environment {raw!r}; inspect environments.json")
    if not raw.replace("-", "").isalnum() or raw.startswith("-") or raw.endswith("-"):
        raise ValueError("Invalid environment ID")
    return raw


def env_root(env_id: str) -> Path:
    env_id = validate_env(env_id)
    # The data parent itself must not redirect every profile at once.
    if DATA_ROOT.is_symlink() or DATA_ROOT.parent.is_symlink():
        raise ValueError(f"Refusing symlink in shared data root: {DATA_ROOT}")
    base = DATA_ROOT.resolve()
    candidate = DATA_ROOT / env_id
    # Never follow an environment-root symlink, even when its target remains
    # somewhere below data/environments: that could alias two consoles' state.
    if candidate.is_symlink():
        raise ValueError(f"Refusing symlink environment root: {candidate}")
    if candidate.exists() and not candidate.is_dir():
        raise ValueError(f"Environment root is not a directory: {candidate}")
    root = candidate.resolve()
    expected = base / env_id
    if root != expected or candidate.parent.resolve() != base:
        raise ValueError(f"Environment root resolves outside its dedicated path: {candidate}")
    return root


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_layout(env_id: str) -> dict[str, str]:
    root = env_root(env_id)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    result = {}
    for name in ALLOWED_DIRS:
        folder = root / name
        if folder.is_symlink():
            raise ValueError(f"Refusing symlink directory: {folder}")
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(folder, 0o700)
        result[name] = str(folder)
    os.chmod(root, 0o700)
    return result


def walk_regular_files(root: Path):
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix().casefold()):
        if path.is_symlink():
            raise ValueError(f"Symlinks are not allowed in storage snapshots: {path}")
        if path.is_file():
            yield path
        elif not path.is_dir():
            raise ValueError(f"Refusing special filesystem object: {path}")


def inspect_env(env_id: str) -> dict[str, Any]:
    root = env_root(env_id)
    layout = {}
    total_files = total_bytes = 0
    disk_images = []
    for name in ALLOWED_DIRS:
        folder = root / name
        files = 0
        size = 0
        if folder.exists() and folder.is_dir() and not folder.is_symlink():
            for path in walk_regular_files(folder):
                stat = path.stat()
                files += 1
                size += stat.st_size
                if path.suffix.lower() in {".qcow2", ".qcow", ".img", ".raw", ".vhd", ".vhdx", ".vmdk"}:
                    disk_images.append({"path": path.relative_to(root).as_posix(), "bytes": stat.st_size, "sha256": sha256_file(path)})
        else:
            layout[name] = {"exists": False, "files": 0, "bytes": 0}
            continue
        total_files += files
        total_bytes += size
        layout[name] = {"exists": True, "files": files, "bytes": size, "path": str(folder)}
    return {"version": VERSION, "environment_id": env_id, "root": str(root), "directories": layout,
            "total_files": total_files, "total_bytes": total_bytes, "disk_images": disk_images,
            "note": "Disk presence is not proof that a valid console OS, firmware, or dashboard is installed."}


def assert_stopped(env_id: str, allow_running: bool = False) -> None:
    if allow_running:
        return
    if not shutil.which("docker"):
        raise RuntimeError("Docker CLI not found; cannot confirm environment is stopped. Install Docker or pass --allow-running only if you accept an inconsistent snapshot.")
    proc = subprocess.run(["docker", "compose", "-f", str(ROOT / "compose.yaml"), "ps", "--status", "running", "--services", f"env-{env_id}"],
                          cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Could not check environment state: {proc.stderr.strip()}")
    if proc.stdout.strip():
        raise RuntimeError(f"env-{env_id} is running. Stop it before backup/restore to avoid an inconsistent snapshot.")


def backup_env(env_id: str, output: Path | None, allow_running: bool) -> Path:
    env_id = validate_env(env_id)
    assert_stopped(env_id, allow_running)
    root = env_root(env_id)
    ensure_layout(env_id)
    files = []
    total = 0
    for path in walk_regular_files(root):
        size = path.stat().st_size
        total += size
        if total > MAX_BACKUP_BYTES:
            raise ValueError("Environment exceeds the configured 2 TiB snapshot safety limit")
        files.append({"path": path.relative_to(root).as_posix(), "size": size, "sha256": sha256_file(path)})
    created = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = output or (BACKUP_ROOT / env_id / f"emustack-{env_id}-{created}.tar.gz")
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = {"format": "emustack-environment-snapshot", "schema_version": 1, "project_version": VERSION,
                "environment_id": env_id, "created_utc": datetime.now(timezone.utc).isoformat(),
                "source_root": f"data/environments/{env_id}", "file_count": len(files), "total_bytes": total, "files": files}
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    tmp = destination.with_name(destination.name + ".partial")
    try:
        with tarfile.open(tmp, "w:gz", compresslevel=5) as archive:
            archive.addfile(_tar_info("manifest.json", len(manifest_bytes)), _BytesReader(manifest_bytes))
            for name in ALLOWED_DIRS:
                path = root / name
                archive.add(path, arcname=f"environment/{env_id}/{name}", recursive=True, filter=_safe_tar_filter)
        tmp.replace(destination)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    os.chmod(destination, 0o600)
    return destination


class _BytesReader:
    """Tiny file-like adapter for tarfile.addfile."""
    def __init__(self, data: bytes): self._data = data; self._offset = 0
    def read(self, n: int = -1) -> bytes:
        if n < 0: n = len(self._data) - self._offset
        chunk = self._data[self._offset:self._offset+n]; self._offset += len(chunk); return chunk


def _tar_info(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = 0o600
    info.mtime = 0
    return info


def _safe_tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    if not (info.isdir() or info.isfile()):
        raise ValueError(f"Refusing to snapshot non-regular file: {info.name}")
    if ".." in PurePosixPath(info.name).parts or PurePosixPath(info.name).is_absolute():
        raise ValueError(f"Unsafe path in snapshot: {info.name}")
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    info.mtime = 0
    return info


def restore_env(env_id: str, archive_path: Path, allow_running: bool) -> Path:
    env_id = validate_env(env_id)
    assert_stopped(env_id, allow_running)
    archive_path = archive_path.expanduser()
    if archive_path.is_symlink():
        raise ValueError("Snapshot must be a regular file, not a symlink")
    archive_path = archive_path.resolve(strict=True)
    if not archive_path.is_file():
        raise ValueError("Snapshot must be a regular file, not a symlink")
    staging_base = STAGING_ROOT.resolve()
    staging_base.mkdir(parents=True, exist_ok=True, mode=0o700)
    stage = Path(tempfile.mkdtemp(prefix=f"restore-{env_id}-", dir=staging_base))
    extracted_root = stage / "environment" / env_id
    expected: dict[str, dict[str, Any]] = {}
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            if len(members) > 250_000:
                raise ValueError("Snapshot has too many entries")
            by_name = {m.name: m for m in members}
            if len(by_name) != len(members):
                raise ValueError("Snapshot contains duplicate paths")
            manifest_member = by_name.get("manifest.json")
            if not manifest_member or not manifest_member.isfile() or manifest_member.size > 32 * 1024 * 1024:
                raise ValueError("Snapshot manifest is missing/invalid")
            manifest_file = archive.extractfile(manifest_member)
            if manifest_file is None:
                raise ValueError("Cannot read snapshot manifest")
            manifest = json.loads(manifest_file.read().decode("utf-8"))
            if manifest.get("format") != "emustack-environment-snapshot" or manifest.get("schema_version") != 1:
                raise ValueError("Unsupported snapshot format")
            if manifest.get("environment_id") != env_id:
                raise ValueError("Snapshot belongs to a different environment")
            for item in manifest.get("files", []):
                rel = PurePosixPath(str(item.get("path", "")))
                if rel.is_absolute() or not rel.parts or any(p in {"", ".", ".."} for p in rel.parts):
                    raise ValueError("Invalid relative path in snapshot manifest")
                if rel.parts[0] not in ALLOWED_DIRS:
                    raise ValueError("Snapshot manifest attempts to write outside allowed environment directories")
                expected[rel.as_posix()] = item
            total = 0
            seen_files: set[str] = set()
            for member in members:
                if member.name == "manifest.json":
                    continue
                pp = PurePosixPath(member.name)
                if pp.is_absolute() or ".." in pp.parts or not member.name.startswith(f"environment/{env_id}/"):
                    raise ValueError(f"Unsafe snapshot path {member.name!r}")
                if not (member.isdir() or member.isfile()):
                    raise ValueError(f"Links and special files are forbidden: {member.name}")
                if member.isfile():
                    rel = PurePosixPath(*pp.parts[2:]).as_posix()
                    if rel not in expected:
                        raise ValueError(f"Unlisted file in snapshot: {rel}")
                    if member.size != int(expected[rel].get("size", -1)):
                        raise ValueError(f"Size mismatch for {rel}")
                    total += member.size
                    if total > MAX_BACKUP_BYTES:
                        raise ValueError("Snapshot exceeds the configured 2 TiB safety limit")
                    source = archive.extractfile(member)
                    if source is None:
                        raise ValueError(f"Cannot read {member.name}")
                    dest = extracted_root / rel
                    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    dest.parent.resolve().relative_to(extracted_root.resolve())
                    digest = hashlib.sha256()
                    with dest.open("xb") as out:
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk: break
                            digest.update(chunk); out.write(chunk)
                    os.chmod(dest, 0o600)
                    if digest.hexdigest() != expected[rel].get("sha256"):
                        raise ValueError(f"SHA-256 mismatch for {rel}")
                    seen_files.add(rel)
                else:
                    rel = PurePosixPath(*pp.parts[2:])
                    if rel.parts and rel.parts[0] not in ALLOWED_DIRS:
                        raise ValueError(f"Unrecognized directory in snapshot: {member.name}")
            if seen_files != set(expected):
                missing = sorted(set(expected) - seen_files)
                raise ValueError(f"Snapshot is incomplete; missing {len(missing)} file(s)")
        # Ensure each subdirectory exists even when empty in the source snapshot.
        for name in ALLOWED_DIRS:
            (extracted_root / name).mkdir(parents=True, exist_ok=True, mode=0o700)
        dest = env_root(env_id)
        rollback_root = DATA_ROOT / f".rollback-{env_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.replace(rollback_root)
        try:
            extracted_root.replace(dest)
        except Exception:
            if rollback_root.exists() and not dest.exists(): rollback_root.replace(dest)
            raise
        os.chmod(dest, 0o700)
        for path in dest.iterdir():
            if path.is_dir(): os.chmod(path, 0o700)
        return rollback_root if rollback_root.exists() else dest
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def create_disk(env_id: str, output: Path | None, size: str, fmt: str) -> Path:
    env_id = validate_env(env_id)
    if fmt not in {"qcow2", "raw"}:
        raise ValueError("Supported disk formats are qcow2 and raw")
    if not shutil.which("qemu-img"):
        raise RuntimeError("qemu-img is missing. Install qemu-utils on the host, then retry.")
    import re
    m = re.fullmatch(r"(\d+)([GgMm])", size)
    if not m:
        raise ValueError("Disk size must be a value such as 8G, 16G, or 512M")
    amount = int(m.group(1)) * (1024**3 if m.group(2).lower() == "g" else 1024**2)
    if not 512 * 1024**2 <= amount <= 128 * 1024**3:
        raise ValueError("Disk size must be between 512 MiB and 128 GiB")
    root = env_root(env_id)
    ensure_layout(env_id)
    target = (output or root / "home" / "disks" / f"{env_id}-data.{fmt}").expanduser().resolve()
    allowed_roots = [(root / "home").resolve(), (root / "saves").resolve()]
    if not any(_is_relative_to(target, r) for r in allowed_roots):
        raise ValueError("For isolation, disk images must be inside this environment's home/ or saves/ directory")
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing disk image: {target}")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    subprocess.run(["qemu-img", "create", "-f", fmt, str(target), str(amount)], check=True)
    os.chmod(target, 0o600)
    print("WARNING: this is a blank data disk only; it contains no console partition table, firmware, games, operating system, or dashboard.", file=sys.stderr)
    return target


def _is_relative_to(path: Path, root: Path) -> bool:
    try: path.relative_to(root); return True
    except ValueError: return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("init", "inspect"):
        sp = sub.add_parser(name); sp.add_argument("environment", nargs="?")
    b = sub.add_parser("backup"); b.add_argument("environment"); b.add_argument("--output", type=Path); b.add_argument("--allow-running", action="store_true")
    r = sub.add_parser("restore"); r.add_argument("environment"); r.add_argument("archive", type=Path); r.add_argument("--allow-running", action="store_true")
    d = sub.add_parser("create-disk"); d.add_argument("environment"); d.add_argument("--output", type=Path); d.add_argument("--size", default="8G"); d.add_argument("--format", choices=("qcow2", "raw"), default="qcow2")
    args = p.parse_args()
    try:
        if args.command == "init":
            ids = [validate_env(args.environment)] if args.environment else sorted(environment_ids())
            result = {env_id: ensure_layout(env_id) for env_id in ids}
            print(json.dumps({"initialized": len(result), "environments": result}, indent=2, ensure_ascii=False))
        elif args.command == "inspect":
            ids = [validate_env(args.environment)] if args.environment else sorted(environment_ids())
            data = [inspect_env(env_id) for env_id in ids]
            print(json.dumps(data[0] if len(data) == 1 else data, indent=2, ensure_ascii=False))
        elif args.command == "backup":
            result = backup_env(args.environment, args.output, args.allow_running)
            print(json.dumps({"snapshot": str(result), "sha256": sha256_file(result)}, indent=2))
        elif args.command == "restore":
            result = restore_env(args.environment, args.archive, args.allow_running)
            print(json.dumps({"restored_environment": args.environment, "previous_environment_backup": str(result)}, indent=2))
        else:
            result = create_disk(args.environment, args.output, args.size, args.format)
            print(json.dumps({"disk_image": str(result), "format": args.format, "size": args.size,
                              "bootable_console_system": False}, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError, tarfile.TarError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
