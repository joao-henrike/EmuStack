#!/usr/bin/env python3
"""Host-side, least-privilege emulator installation manager for EmuStack.

Works on the host, never in dashboard containers. Does not fetch code, ROMs,
BIOS, firmware or proprietary assets. Compiling third-party sources requires
an explicit opt-in and runs programs on the host; review upstream beforehand.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "emulator-manager"
SOURCE_LOCK = ROOT / "upstream" / "source-lock.json"
CATALOG = ROOT / "catalog.json"
RELEASE_LOCK = ROOT / "release-lock.json"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")

# These are the only reviewed Linux build entrypoints. Other pinned sources
# remain accessible for audit and manual research, not arbitrary execution.
RECIPES = {
    "shadps4": {
        "source": "shadps4",
        "name": "shadPS4",
        "requires": ["git", "cmake", "ninja", "cc", "c++"],
        "packages": "build-essential cmake ninja-build libx11-dev libxext-dev libwayland-dev libxkbcommon-dev libxcursor-dev libxi-dev libxss-dev libxtst-dev libxrandr-dev libxfixes-dev libudev-dev libevdev-dev libasound2-dev libpulse-dev libopenal-dev libssl-dev libvulkan-dev libpng-dev",
        "reference": "https://github.com/shadps4-emu/shadPS4/blob/main/documents/building-linux.md",
        "artifacts": ["build/shadps4"],
    },
    "ppsspp": {
        "source": "ppsspp",
        "name": "PPSSPPSDL",
        "requires": ["git", "cmake", "ninja", "c++"],
        "packages": "cmake ninja-build build-essential libsdl2-dev libsdl2-ttf-dev libfontconfig1-dev libcurl4-openssl-dev libglew-dev",
        "reference": "https://github.com/hrydgard/ppsspp/wiki/Build-instructions",
        "artifacts": ["build/PPSSPPSDL", "build/PPSSPPQt"],
    },
    "melonds": {
        "source": "melonds",
        "name": "melonDS",
        "requires": ["git", "cmake", "ninja", "c++"],
        "packages": "cmake ninja-build build-essential extra-cmake-modules libsdl2-dev libarchive-dev libenet-dev libzstd-dev libfaad-dev libpcap0.8-dev qt6-base-dev qt6-base-private-dev qt6-multimedia-dev libqt6svg6-dev",
        "reference": "https://github.com/melonDS-emu/melonDS/blob/master/BUILD.md",
        "artifacts": ["build/melonDS", "build/src/melonDS"],
    },
    "bsnes": {
        "source": "bsnes",
        "name": "bsnes",
        "requires": ["git", "make", "c++"],
        "packages": "build-essential libsdl2-dev libgtk-3-dev libgtksourceview-3.0-dev libao-dev libopenal-dev",
        "reference": "https://github.com/bsnes-emu/bsnes/blob/master/docs/how-to/build-from-source.md",
        "artifacts": ["source/bsnes/out/bsnes", "source/bsnes/out/bsnes.bin"],
    },
}


class ManagerError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ManagerError(f"Invalid JSON object: {path}")
    return data


def profiles() -> dict[str, dict]:
    items = load_json(CATALOG).get("emulators", [])
    if len(items) != 20 or len({p["id"] for p in items}) != 20:
        raise ManagerError("Expected 20 unique EmuStack catalog profiles")
    return {p["id"]: p for p in items}


def source_map() -> dict[str, dict]:
    items = load_json(SOURCE_LOCK).get("sources", [])
    return {s["id"]: s for s in items}


def profile(identifier: str) -> dict:
    catalog = profiles()
    if identifier not in catalog:
        raise ManagerError(f"Unknown emulator profile: {identifier}")
    return catalog[identifier]


def supported(item: dict) -> bool:
    return item.get("runtime") not in {"unsupported", "research-project", "windows-only"} and item.get("game_arg") != "blocked"


def check_managed_path(path: Path) -> None:
    """Protect fixed project-owned writable roots from symlink redirection."""
    root = ROOT.resolve(strict=True)
    if not path.is_relative_to(ROOT):
        raise ManagerError(f"Outside project: {path}")
    current = path
    while current != ROOT:
        if current.is_symlink():
            raise ManagerError(f"Refusing symlink in managed path: {current}")
        current = current.parent
    if ROOT.is_symlink() or ROOT.resolve(strict=True) != root:
        raise ManagerError("Repository root cannot be a symlink")


def ensure_dir(path: Path) -> None:
    check_managed_path(path)
    path.mkdir(parents=True, exist_ok=True)


def hash_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            sha.update(block)
    return sha.hexdigest()


def destination(identifier: str, name: str) -> Path:
    item = profile(identifier)
    if not supported(item):
        raise ManagerError(f"{identifier} has no supported EmuStack runner")
    if name not in item.get("binary_names", []):
        raise ManagerError(f"Executable name {name!r} is not allowlisted for {identifier}")
    path = ROOT / "data" / "environments" / identifier / "emulators" / name
    check_managed_path(path)
    return path


def record_file(identifier: str) -> Path:
    path = STATE / "active" / f"{identifier}.json"
    check_managed_path(path)
    return path


def active(identifier: str) -> dict | None:
    path = record_file(identifier)
    return load_json(path) if path.is_file() else None


def write_record(identifier: str, record: dict | None) -> None:
    path = record_file(identifier)
    ensure_dir(path.parent)
    if record is None:
        path.unlink(missing_ok=True)
        return
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".meta-", delete=False) as stream:
        temp = Path(stream.name)
        try:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    os.replace(temp, path)


def previous_dir(identifier: str) -> Path:
    path = STATE / "versions" / identifier
    check_managed_path(path)
    return path


def backup_current(identifier: str, target: Path) -> Path | None:
    if not target.is_file():
        return None
    ensure_dir(previous_dir(identifier))
    name = f"{time.time_ns()}-{hash_file(target)}.bin"
    backup = previous_dir(identifier) / name
    os.replace(target, backup)
    return backup


def install_artifact(identifier: str, file: Path, name: str, origin: dict,
                     expected_sha: str | None = None) -> dict:
    """Atomically deploy an allowlisted filename, retaining the old binary."""
    dest = destination(identifier, name)
    current = active(identifier)
    if current and current.get("binary_name") != name:
        raise ManagerError(
            f"Profile {identifier} already manages {current['binary_name']}; "
            "uninstall that installation before changing executable names"
        )
    if dest.is_file():
        if not current or current.get("sha256") != hash_file(dest):
            raise ManagerError("Existing executable is unmanaged or modified; refusing to overwrite")
    if file.is_symlink() or not file.is_file():
        raise ManagerError(f"Input must be a regular file, not a link: {file}")
    src = file.resolve(strict=True)
    if src == dest:
        raise ManagerError("Cannot import an already active executable")
    actual = hash_file(file)
    if expected_sha is not None and (not HEX64.fullmatch(expected_sha) or actual != expected_sha):
        raise ManagerError("SHA-256 mismatch; no files changed")
    if dest.is_symlink():
        raise ManagerError("Refusing to replace a symlinked executable")
    ensure_dir(dest.parent)
    # Write on the same filesystem as the destination for atomic promotion.
    fd, temp_name = tempfile.mkstemp(prefix=".emustack-new-", dir=dest.parent)
    temp = Path(temp_name)
    backup = None
    try:
        with os.fdopen(fd, "wb") as output, file.open("rb") as source:
            shutil.copyfileobj(source, output, 1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        if hash_file(temp) != actual:
            raise ManagerError("Copy verification failed")
        temp.chmod(0o755)
        backup = backup_current(identifier, dest)
        try:
            os.replace(temp, dest)
        except BaseException:
            if backup is not None:
                os.replace(backup, dest)
            raise
        record = {
            "schema_version": 1, "profile": identifier, "binary_name": name,
            "sha256": actual, "installed_at": now(), "origin": origin,
            "validation": "file-hash-only", "runtime_tested": False,
        }
        try:
            write_record(identifier, record)
        except BaseException:
            # The previous active metadata remains intact if state persistence fails.
            if backup is not None:
                os.replace(backup, dest)
            else:
                dest.unlink(missing_ok=True)
            raise
        tombstone_file(identifier).unlink(missing_ok=True)
        return {"installed": str(dest.relative_to(ROOT)), "sha256": actual,
                "previous_backup": str(backup.relative_to(ROOT)) if backup else None,
                "runtime_tested": False}
    finally:
        temp.unlink(missing_ok=True)


def verify_source(identifier: str) -> tuple[Path, dict]:
    recipe = RECIPES[identifier]
    item = source_map().get(recipe["source"])
    if not item or not HEX40.fullmatch(item.get("commit", "")):
        raise ManagerError("Source lock does not contain the expected SHA")
    src = ROOT / item["path"]
    check_managed_path(src)
    if not src.is_dir() or not (src / ".git").exists():
        raise ManagerError(f"Source checkout missing: {src}. Run upstream-manager.py sync")
    def git(*args: str) -> str:
        result = subprocess.run(["git", "-C", str(src), *args], capture_output=True,
                                text=True, timeout=30, check=False)
        if result.returncode:
            raise ManagerError(result.stderr.strip() or "Cannot inspect source")
        return result.stdout.strip()
    head = git("rev-parse", "HEAD")
    staged = subprocess.run(["git", "ls-files", "--stage", "--", item["path"]],
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    if head != item["commit"] or staged != f"160000 {head} 0\t{item['path']}":
        raise ManagerError(f"Source/index does not match immutable pin for {identifier}")
    if git("status", "--porcelain"):
        raise ManagerError(f"Dirty upstream source: {identifier}; clean or resync before building")
    nested = git("submodule", "status", "--recursive")
    if any(line and line[0] in "-+U" for line in nested.splitlines()):
        raise ManagerError(
            f"Nested dependencies missing/mismatched in {identifier}; review the upstream "
            "dependencies and initialize required submodules explicitly before building"
        )
    return src, item


def dependencies(identifier: str) -> dict:
    item = profile(identifier)
    recipe = RECIPES.get(identifier)
    if recipe is None:
        return {"id": identifier, "source_build": "not-integrated",
                "binary_install": "official-release-lock-or-reviewed-local-file" if supported(item) else "unsupported"}
    missing = [command for command in recipe["requires"] if shutil.which(command) is None]
    return {"id": identifier, "source_build": "configured", "missing_commands": missing,
            "debian_build_packages": recipe["packages"], "upstream_build_reference": recipe["reference"],
            "source_commit": source_map()[recipe["source"]]["commit"],
            "note": "Native development packages are not installed automatically; examine upstream instructions."}


def toolchain_info() -> dict:
    """Capture tool versions without running untrusted emulator binaries."""
    versions = {}
    for executable in ("cmake", "ninja", "c++", "cc", "make"):
        path = shutil.which(executable)
        if path is None:
            continue
        try:
            result = subprocess.run([path, "--version"], capture_output=True, text=True,
                                    timeout=5, check=False)
            if result.returncode == 0:
                versions[executable] = result.stdout.splitlines()[0][:200]
        except (OSError, subprocess.TimeoutExpired, IndexError):
            continue
    return versions


def run_build(args: list[str], work: Path, log: Path, env: dict | None = None) -> None:
    with log.open("a", encoding="utf-8") as stream:
        stream.write(f"\n$ {json.dumps(args)}\n")
        stream.flush()
        result = subprocess.run(args, cwd=work, stdout=stream, stderr=subprocess.STDOUT,
                                env=env, timeout=3600, check=False)
        if result.returncode != 0:
            raise ManagerError(f"Build command failed ({result.returncode}); inspect {log.relative_to(ROOT)}")


def build(identifier: str, jobs: int, yes: bool) -> dict:
    if identifier not in RECIPES:
        raise ManagerError(f"No reviewed source-build recipe for {identifier}; use an official pinned release instead")
    if not yes:
        raise ManagerError("Building executes third-party code on the host. Review the source; add --yes-run-upstream-code to authorize.")
    if os.geteuid() == 0:
        raise ManagerError("Do not compile upstream code as root")
    if not 1 <= jobs <= 8:
        raise ManagerError("--jobs must be 1..8")
    report = dependencies(identifier)
    if report["missing_commands"]:
        raise ManagerError("Missing commands: " + ", ".join(report["missing_commands"]))
    src, pin = verify_source(identifier)
    ensure_dir(STATE / "logs")
    ensure_dir(STATE / "work")
    log = STATE / "logs" / f"{identifier}-{time.time_ns()}.log"
    with tempfile.TemporaryDirectory(prefix=f"{identifier}-", dir=STATE / "work") as scratch:
        work = Path(scratch)
        # Building only in a disposable copy avoids dirtying pinned submodules.
        shutil.copytree(src, work / "source", symlinks=True,
                        ignore=shutil.ignore_patterns(".git"))
        cloned = work / "source"
        for link in cloned.rglob("*"):
            if link.is_symlink() and not link.resolve(strict=False).is_relative_to(cloned):
                raise ManagerError("Upstream symlink points outside the staged source: "
                                   + str(link.relative_to(cloned)))
        if identifier == "bsnes":
            run_build(["make", "-C", str(cloned / "bsnes"), "build=release",
                       "local=false", f"-j{jobs}"], work, log)
        else:
            args = ["cmake", "-S", str(cloned), "-B", str(work / "build"),
                    "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"]
            if identifier == "melonds":
                args.append("-DCMAKE_INSTALL_PREFIX=/usr")
            run_build(args, work, log)
            run_build(["cmake", "--build", str(work / "build"), "--parallel", str(jobs)], work, log)
        candidates = [work / p for p in RECIPES[identifier]["artifacts"]]
        binary = next((p for p in candidates if p.is_file() and not p.is_symlink()), None)
        if binary is None:
            raise ManagerError(f"Expected executable not produced; inspect {log.relative_to(ROOT)}")
        if binary.stat().st_size == 0:
            raise ManagerError("Build produced an empty binary")
        return install_artifact(identifier, binary, RECIPES[identifier]["name"], {
            "method": "pinned-source-build", "source": pin["url"],
            "commit": pin["commit"], "build_log": str(log.relative_to(ROOT)),
            "host": {"os": platform.system(), "architecture": platform.machine(),
                     "python": platform.python_version()},
            "toolchain": toolchain_info(),
            "warning": "Binary existence is not proof of runtime compatibility; resources may still be required.",
        })


def history(identifier: str) -> list[dict]:
    profile(identifier)
    folder = previous_dir(identifier)
    if not folder.is_dir():
        return []
    records = []
    for file in sorted(folder.glob("*.bin"), reverse=True):
        if file.is_symlink() or not file.is_file():
            continue
        sha = hash_file(file)
        records.append({"file": file.name, "sha256": sha, "size": file.stat().st_size})
    return records


def tombstone_file(identifier: str) -> Path:
    profile(identifier)
    path = STATE / "removed" / f"{identifier}.json"
    check_managed_path(path)
    return path


def rollback(identifier: str) -> dict:
    record = active(identifier)
    if not record:
        tombstone = tombstone_file(identifier)
        if tombstone.is_file():
            record = load_json(tombstone)
    if not record:
        raise ManagerError(f"No manager-controlled installation to roll back: {identifier}")
    versions = history(identifier)
    if not versions:
        raise ManagerError(f"No previous installation stored: {identifier}")
    candidate = previous_dir(identifier) / versions[0]["file"]
    return install_artifact(identifier, candidate, record["binary_name"],
                            {"method": "rollback", "from": versions[0]["file"]},
                            versions[0]["sha256"])


def uninstall(identifier: str) -> dict:
    record = active(identifier)
    if not record:
        raise ManagerError(f"No manager-controlled installation to uninstall: {identifier}")
    dest = destination(identifier, record["binary_name"])
    if dest.is_symlink() or not dest.is_file() or hash_file(dest) != record["sha256"]:
        raise ManagerError("Managed executable modified or missing; refusing to delete it")
    backup = backup_current(identifier, dest)
    tombstone = tombstone_file(identifier)
    ensure_dir(tombstone.parent)
    # A removal record allows rollback even after uninstall; active stays absent.
    tombstone.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_record(identifier, None)
    return {"removed": identifier, "rollback_backup": str(backup.relative_to(ROOT))}


def inspect_binary(path: Path) -> dict:
    """Read file signatures and ELF machine without executing the executable."""
    with path.open("rb") as stream:
        prefix = stream.read(64)
    if prefix.startswith(b"\x7fELF") and len(prefix) >= 20:
        endian = "little" if prefix[5] == 1 else "big" if prefix[5] == 2 else None
        machine = int.from_bytes(prefix[18:20], endian) if endian else 0
        return {"format": "ELF", "elf_machine": machine,
                "architecture_hint": {62: "x86_64", 183: "aarch64", 3: "i386"}.get(machine, "unknown")}
    if prefix.startswith(b"MZ"):
        return {"format": "possible-PE-Windows", "architecture_hint": "not-checked"}
    if prefix.startswith(b"#!"):
        return {"format": "script", "architecture_hint": "interpreted"}
    return {"format": "unknown", "architecture_hint": "unknown"}


def status(identifier: str | None = None) -> list[dict]:
    result = []
    lock_modes = {key: value.get("mode") for key, value
                  in load_json(RELEASE_LOCK).get("items", {}).items()}
    mapped = {s["profile"] for s in source_map().values()}
    for name, item in profiles().items():
        if identifier is not None and name != identifier:
            continue
        current = active(name)
        checked = None
        signature = None
        if current:
            target = destination(name, current["binary_name"])
            if target.is_file() and not target.is_symlink():
                checked = hash_file(target) == current["sha256"]
                signature = inspect_binary(target)
            else:
                checked = False
        result.append({
            "id": name,
            "runtime": item.get("runtime"),
            "official_release_lock": lock_modes.get(name, "not-declared"),
            "source_pinned": name in mapped,
            "source_build": name in RECIPES,
            "managed_install": current,
            "managed_hash_valid": checked,
            "binary_signature": signature,
            "previous_versions": len(history(name)),
            "availability": "not-checked-in-host-runtime",
            "execution_tested": False,
        })
    if identifier is not None and not result:
        raise ManagerError("Unknown emulator profile")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("status", "deps", "history", "rollback", "uninstall"):
        p = sub.add_parser(action)
        p.add_argument("id", nargs="?" if action == "status" else None)
    p = sub.add_parser("build", help="compile one reviewed source recipe")
    p.add_argument("id", choices=sorted(RECIPES))
    p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--yes-run-upstream-code", action="store_true")
    all_parser = sub.add_parser("build-all", help="try all reviewed builds independently; report every failure")
    all_parser.add_argument("--jobs", type=int, default=2)
    all_parser.add_argument("--yes-run-upstream-code", action="store_true")
    p = sub.add_parser("install-file", help="import reviewed binary into private emulator profile")
    p.add_argument("id")
    p.add_argument("file", type=Path)
    p.add_argument("--sha256", required=True)
    p.add_argument("--binary-name", required=True)
    args = parser.parse_args()
    try:
        if args.action == "status":
            data = status(args.id)
        elif args.action == "deps":
            data = dependencies(args.id)
        elif args.action == "history":
            data = history(args.id)
        elif args.action == "build":
            data = build(args.id, args.jobs, args.yes_run_upstream_code)
        elif args.action == "build-all":
            if not args.yes_run_upstream_code:
                raise ManagerError("Review all upstream sources and pass --yes-run-upstream-code")
            results = {}
            for identifier in RECIPES:
                try:
                    results[identifier] = {"status": "installed", "result": build(identifier, args.jobs, True)}
                except (ManagerError, OSError, subprocess.SubprocessError) as exc:
                    results[identifier] = {"status": "failed", "error": str(exc)}
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return 1 if any(item["status"] != "installed" for item in results.values()) else 0
        elif args.action == "install-file":
            data = install_artifact(args.id, args.file, args.binary_name,
                                    {"method": "reviewed-local-file", "input_name": args.file.name},
                                    args.sha256)
        elif args.action == "rollback":
            data = rollback(args.id)
        else:
            data = uninstall(args.id)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    except (ManagerError, OSError, ValueError, KeyError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"EMUSTACK MANAGER ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
