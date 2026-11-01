#!/usr/bin/env python3
"""Host-side, least-privilege emulator installation manager for EmuStack.

Works on the host, never in dashboard containers. Does not fetch code, ROMs,
BIOS, firmware or proprietary assets. Compiling third-party sources requires
an explicit opt-in and runs programs on the host; review upstream beforehand.
"""
from __future__ import annotations

import argparse
import configparser
from collections import deque
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "emulator-manager"
SOURCE_LOCK = ROOT / "upstream" / "source-lock.json"
CATALOG = ROOT / "catalog.json"
RELEASE_LOCK = ROOT / "release-lock.json"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
TRUSTED_SUBMODULE_HOSTS = frozenset({"github.com", "android.googlesource.com"})

# These are the only reviewed Linux build entrypoints. Other pinned sources
# remain accessible for audit and manual research, not arbitrary execution.
RECIPES = {
    "kytyps5": {
        "source": "kytyps5",
        "name": "kyty_launcher",
        "requires": ["git", "cmake", "ninja", "clang", "clang++", "glslangValidator", "pkg-config"],
        "pkg_config_required": ["Qt6Core", "Qt6Widgets", "Qt6Network", "Qt6Concurrent"],
        "qt6_min": "6.8",
        "packages": "clang lld cmake ninja-build git glslang-tools python3 pkg-config qt6-base-dev libgl1-mesa-dev libx11-dev libxcursor-dev libxext-dev libxfixes-dev libxi-dev libxrandr-dev libxss-dev libxtst-dev libxkbcommon-dev libasound2-dev libpulse-dev libudev-dev libdbus-1-dev libwayland-dev wayland-protocols",
        "reference": "https://github.com/KytyPS5/KytyPS5#building-on-linux",
        "artifacts": ["package/kyty_launcher", "package/launcher", "build/kyty_launcher"],
    },
    "shadps4": {
        "source": "shadps4",
        "name": "shadPS4",
        "requires": ["git", "cmake", "ninja", "cc", "c++"],
        "cmake_min": "3.26",
        "packages": "build-essential cmake ninja-build libx11-dev libxext-dev libwayland-dev libxkbcommon-dev libxcursor-dev libxi-dev libxss-dev libxtst-dev libxrandr-dev libxfixes-dev libudev-dev libevdev-dev libasound2-dev libpulse-dev libopenal-dev libssl-dev libvulkan-dev libpng-dev",
        "reference": "https://github.com/shadps4-emu/shadPS4/blob/main/documents/building-linux.md",
        "artifacts": ["build/shadps4"],
    },
    "ppsspp": {
        "source": "ppsspp",
        "name": "PPSSPPSDL",
        "requires": ["git", "cmake", "ninja", "c++", "pkg-config"],
        "pkg_config_required": ["sdl3", "SDL3_ttf"],
        "packages": "cmake ninja-build build-essential pkg-config libsdl3-dev libsdl3-ttf-dev libfontconfig1-dev libcurl4-openssl-dev libglew-dev",
        "reference": "https://github.com/hrydgard/ppsspp/wiki/Build-instructions",
        "artifacts": ["build/PPSSPPSDL", "build/PPSSPPQt"],
    },
    "melonds": {
        "source": "melonds",
        "name": "melonDS",
        "requires": ["git", "cmake", "ninja", "c++", "pkg-config"],
        "pkg_config_required": ["Qt6Core", "Qt6Widgets", "Qt6Multimedia", "Qt6Svg", "sdl2", "libarchive", "libzstd", "faad2"],
        "packages": "cmake ninja-build build-essential pkg-config extra-cmake-modules libsdl2-dev libarchive-dev libenet-dev libzstd-dev libfaad-dev libpcap0.8-dev libcurl4-gnutls-dev qt6-base-dev qt6-base-private-dev qt6-multimedia-dev libqt6svg6-dev libwayland-dev",
        "reference": "https://github.com/melonDS-emu/melonDS/blob/master/BUILD.md",
        "artifacts": ["build/melonDS", "build/src/melonDS"],
    },
    "bsnes": {
        "source": "bsnes",
        "name": "bsnes",
        "requires": ["git", "make", "c++", "pkg-config"],
        "pkg_config_required": ["gtk+-3.0", "sdl2"],
        "packages": "build-essential pkg-config libsdl2-dev libgtk-3-dev libx11-dev libxext-dev libxrandr-dev libgtksourceview-3.0-dev libao-dev libopenal-dev",
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
    if not path.is_absolute() or ".." in path.parts or not path.resolve(strict=False).is_relative_to(root):
        raise ManagerError(f"Outside project or unsafe traversal: {path}")
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

    previous = active(identifier)
    os.replace(target, backup)
    if previous and previous.get("sha256") == backup.name.split("-")[-1].removesuffix(".bin"):
        # Keep provenance (especially bundle ID) with the previous executable.
        metadata = backup.with_suffix(".json")
        try:
            metadata.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except BaseException:
            os.replace(backup, target)
            raise
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


def verify_source(identifier: str, *, require_nested: bool = True) -> tuple[Path, dict]:
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
    if require_nested:
        nested = git("submodule", "status", "--recursive")
        problems = [
            line[:220] for line in nested.splitlines() if line and line[0] in "-+U"
        ]
        if problems:
            raise ManagerError(
                f"Nested dependencies missing/mismatched in {identifier}: "
                + " | ".join(problems[:5])
                + ". Run: python3 scripts/emulator-manager.py sync-deps "
                + identifier + " --yes-download-submodules"
            )
    return src, item



def submodule_entries(repo_dir: Path) -> list[tuple[str, str]]:
    """Audit .gitmodules paths, URLs and index gitlinks before any network access."""
    manifest = repo_dir / ".gitmodules"
    if not manifest.exists():
        return []
    if manifest.is_symlink():
        raise ManagerError("Refusing symlinked .gitmodules file")
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.read(manifest, encoding="utf-8")
    entries = []
    for section in config.sections():
        if not section.startswith('submodule "') or not section.endswith('"'):
            raise ManagerError("Unexpected .gitmodules section: " + section)
        path = config.get(section, "path", fallback="")
        url = config.get(section, "url", fallback="")
        parts = Path(path)
        if (not path or parts.is_absolute() or
                any(part in ("", ".", "..") for part in parts.parts) or
                not re.fullmatch(r"[A-Za-z0-9_./-]+", path) or
                "\\" in path):
            raise ManagerError("Unsafe submodule path: " + repr(path))
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in TRUSTED_SUBMODULE_HOSTS or
                parsed.username or parsed.password or parsed.port or parsed.query or
                parsed.fragment or not parsed.path.startswith("/") or not parsed.path.strip("/")):
            raise ManagerError("Unreviewed submodule origin: " + repr(url))
        staged = subprocess.run(
            ["git", "-C", str(repo_dir), "ls-files", "--stage", "--", path],
            capture_output=True, text=True, timeout=30, check=True
        ).stdout.strip()
        if not re.fullmatch(r"160000 [0-9a-f]{40} 0\t" + re.escape(path), staged):
            raise ManagerError("Missing pinned gitlink for submodule: " + path)
        target = repo_dir / path
        if not target.resolve(strict=False).is_relative_to(repo_dir.resolve()):
            raise ManagerError("Submodule target escapes repository: " + path)
        current = target
        while current != repo_dir:
            if current.is_symlink():
                raise ManagerError("Symlink in nested submodule path: " + path)
            current = current.parent
        entries.append((path, url))
    return entries



def plan_deps(identifier: str) -> dict:
    """Inspect the first-level remote URLs and exact gitlink commits, without fetching."""
    if identifier not in RECIPES:
        raise ManagerError("No source build recipe for " + identifier)
    root, pin = verify_source(identifier, require_nested=False)
    entries = submodule_entries(root)
    return {
        "profile": identifier, "parent_commit": pin["commit"],
        "first_level": [
            {
                "path": path, "url": url,
                "commit": subprocess.run(
                    ["git", "-C", str(root), "ls-files", "--stage", "--", path],
                    capture_output=True, text=True, timeout=30, check=True
                ).stdout.strip().split()[1],
            }
            for path, url in entries
        ],
        "note": "First-level plan only. Deeper submodules are audited before each level is fetched.",
    }


def sync_deps(identifier: str, jobs: int, allow_download: bool) -> dict:
    """Explicit, bounded walk of upstream-pinned submodules; never chase HEAD."""
    if identifier not in RECIPES:
        raise ManagerError("No reviewed source-build recipe for " + identifier)
    if not allow_download:
        raise ManagerError("Review nested upstream origins; pass --yes-download-submodules to fetch pinned dependencies")
    if os.geteuid() == 0:
        raise ManagerError("Do not download upstream source as root")
    if not 1 <= jobs <= 4:
        raise ManagerError("--jobs must be between 1 and 4 for nested source synchronization")
    root, parent_lock = verify_source(identifier, require_nested=False)
    queue = deque([(root, 0)])
    fetched = 0
    inspected = 0
    while queue:
        repo_dir, depth = queue.popleft()
        # Fail closed before touching new unreviewed nested repositories.
        entries = submodule_entries(repo_dir)
        if not entries:
            continue
        if depth >= 4 or inspected + len(entries) > 160:
            raise ManagerError("Nested source depth/count limit reached; inspect repositories manually")
        inspected += len(entries)
        paths = [path for path, url in entries]
        # Synchronize local config to the already-audited .gitmodules URLs.
        # Disable non-HTTPS protocols even if a user config enabled them.
        commands = [
            ["git", "-c", "protocol.file.allow=never",
             "-c", "protocol.ext.allow=never", "-c", "protocol.ssh.allow=never",
             "-c", "protocol.git.allow=never", "-C", str(repo_dir),
             "submodule", "sync", "--", *paths],
            ["git", "-c", "protocol.file.allow=never",
             "-c", "protocol.ext.allow=never", "-c", "protocol.ssh.allow=never",
             "-c", "protocol.git.allow=never", "-C", str(repo_dir),
             "submodule", "update", "--init", f"--jobs={jobs}", "--", *paths],
        ]
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=7200, check=False)
            if result.returncode:
                error_tail = (result.stderr or result.stdout).strip()[-1200:]
                raise ManagerError("Nested sync failed at " + str(repo_dir.relative_to(ROOT))
                                   + ": " + error_tail)
        for path, _url in entries:
            child = repo_dir / path
            if child.is_symlink() or not child.is_dir():
                raise ManagerError("Missing or symlinked nested checkout: " + path)
            # A checkout must have the exact index-locked gitlink commit.
            expect = subprocess.run(
                ["git", "-C", str(repo_dir), "ls-files", "--stage", "--", path],
                capture_output=True, text=True, timeout=30, check=True
            ).stdout.strip().split()[1]
            actual = subprocess.run(
                ["git", "-C", str(child), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=30, check=True
            ).stdout.strip()
            if actual != expect:
                raise ManagerError("Unexpected nested commit for " + path)
            queue.append((child, depth + 1))
            fetched += 1
    verify_source(identifier)
    return {
        "profile": identifier, "parent_commit": parent_lock["commit"],
        "nested_checkouts_verified": fetched,
        "gitlinks_audited": inspected,
        "status": "pinned-nested-source-ready",
        "note": "Only audited HTTPS remotes and index-pinned gitlink commits used; no build performed",
    }


def dependencies(identifier: str) -> dict:
    item = profile(identifier)
    recipe = RECIPES.get(identifier)
    if recipe is None:
        return {"id": identifier, "source_build": "not-integrated",
                "binary_install": "official-release-lock-or-reviewed-local-file" if supported(item) else "unsupported"}
    missing = [command for command in recipe["requires"] if shutil.which(command) is None]
    modules = recipe.get("pkg_config_required", [])
    missing_modules = []
    if modules:
        pkg_config = shutil.which("pkg-config")
        if pkg_config is None:
            if "pkg-config" not in missing:
                missing.append("pkg-config")
            missing_modules = list(modules)
        else:
            for module in modules:
                probe = subprocess.run([pkg_config, "--exists", module],
                                       capture_output=True, timeout=10, check=False)
                if probe.returncode:
                    missing_modules.append(module)
    version_blockers = []
    for tool_name, required in (("cmake", recipe.get("cmake_min")),
                                ("Qt6Core", recipe.get("qt6_min"))):
        if not required:
            continue
        if tool_name == "cmake":
            binary = shutil.which("cmake")
            cmd = [binary, "--version"] if binary else None
        else:
            binary = shutil.which("pkg-config")
            cmd = [binary, "--modversion", "Qt6Core"] if binary and "Qt6Core" not in missing_modules else None
        if cmd is None:
            continue
        try:
            probe = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
            raw = (probe.stdout or "").strip()
            match = re.search(r"([0-9]+)\.([0-9]+)(?:\.([0-9]+))?", raw)
            req = tuple(int(x) for x in (required.split(".") + ["0", "0"])[:3])
            found = tuple(int(x or 0) for x in match.groups()) if match and probe.returncode == 0 else None
            if found is None or found < req:
                version_blockers.append({"tool": tool_name, "required": required, "found": raw[:100] or "unknown"})
        except (OSError, subprocess.TimeoutExpired):
            version_blockers.append({"tool": tool_name, "required": required, "found": "probe-failed"})
    return {
        "id": identifier, "source_build": "configured",
        "missing_commands": missing, "missing_pkg_config": missing_modules,
        "insufficient_versions": version_blockers,
        "debian_build_packages": recipe["packages"],
        "upstream_build_reference": recipe["reference"],
        "source_commit": source_map()[recipe["source"]]["commit"],
        "note": "Command checks and selected pkg-config probes only; optional or undocumented "
                "library dependencies may still be missing. Nothing is installed automatically.",
    }



def stage_git_metadata(original: Path, staged: Path) -> dict:
    """Create independent staging Git metadata backed by read-only pinned objects.

    Original source Git directories are not copied or altered. Staged checkouts
    retain their real commit identities, including nested FFmpeg gitlinks, so
    upstream CMake git rev-parse cannot accidentally discover EmuStack HEAD.
    """
    queue = deque([(original, staged, 0)])
    initialized = 0
    while queue:
        origin, destination_path, depth = queue.popleft()
        if depth > 4 or initialized >= 161:
            raise ManagerError("Staged nested repository depth/count exceeded")
        if destination_path.is_symlink() or not destination_path.is_dir():
            raise ManagerError("Missing or symlinked staged Git tree: " + str(destination_path))
        def inspect(*git_args: str) -> str:
            p = subprocess.run(
                ["git", "-C", str(origin), *git_args],
                capture_output=True, text=True, timeout=60, check=True
            )
            return p.stdout.strip()
        commit = inspect("rev-parse", "HEAD")
        if not HEX40.fullmatch(commit):
            raise ManagerError("Invalid pinned upstream commit while staging")
        git_dir = Path(inspect("rev-parse", "--absolute-git-dir")).resolve(strict=True)
        original_objects = (git_dir / "objects").resolve(strict=True)
        if not original_objects.is_dir():
            raise ManagerError("Missing original Git object database")
        if (destination_path / ".git").exists() or (destination_path / ".git").is_symlink():
            raise ManagerError("Staging unexpectedly contains .git metadata")
        subprocess.run(["git", "init", "-q", str(destination_path)],
                       capture_output=True, text=True, timeout=30, check=True)
        alternates = destination_path / ".git" / "objects" / "info" / "alternates"
        alternates.parent.mkdir(parents=True, exist_ok=True)
        alternates.write_text(str(original_objects) + "\n", encoding="utf-8")
        # Populate staging refs/index using the real immutable upstream object.
        for git_args in (("read-tree", commit), ("update-ref", "HEAD", commit)):
            subprocess.run(["git", "-C", str(destination_path), *git_args],
                           capture_output=True, text=True, timeout=60, check=True)
        if subprocess.run(
            ["git", "-C", str(destination_path), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30, check=True
        ).stdout.strip() != commit:
            raise ManagerError("Staged Git HEAD differs from pinned source commit")
        initialized += 1
        for path, _url in submodule_entries(origin):
            child = origin / path
            staged_child = destination_path / path
            if child.is_symlink() or not child.is_dir():
                raise ManagerError("Nested dependency not initialized: " + path)
            queue.append((child, staged_child, depth + 1))
    return {"staged_git_repositories": initialized, "original_git_metadata_modified": False}


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
            with log.open("r", encoding="utf-8", errors="replace") as output:
                tail = "".join(deque(output, maxlen=18)).rstrip()[-3500:]
            raise ManagerError(
                f"Build command failed ({result.returncode}); log: "
                f"{log.relative_to(ROOT)}\n--- last log lines ---\n{tail}"
            )


def build(identifier: str, jobs: int, yes: bool) -> dict:
    if identifier not in RECIPES:
        raise ManagerError(f"No reviewed source-build recipe for {identifier}; use an official pinned release instead")
    if not yes:
        raise ManagerError("Building executes reviewed third-party code; prefer the Docker-first scripts/phase1.sh wrapper and add --yes-run-upstream-code.")
    if os.geteuid() == 0:
        raise ManagerError("Do not compile upstream code as root")
    if not 1 <= jobs <= 8:
        raise ManagerError("--jobs must be 1..8")
    report = dependencies(identifier)
    if report["missing_commands"] or report["missing_pkg_config"] or report.get("insufficient_versions"):
        problems = []
        if report["missing_commands"]:
            problems.append("commands: " + ", ".join(report["missing_commands"]))
        if report["missing_pkg_config"]:
            problems.append("pkg-config modules: " + ", ".join(report["missing_pkg_config"]))
        if report.get("insufficient_versions"):
            problems.extend("version: {tool} >= {required} (found {found})".format(**item)
                            for item in report["insufficient_versions"])
        raise ManagerError(
            "Missing build dependencies for " + identifier + " (" + "; ".join(problems) + "). "
            "Review required packages with: python3 scripts/emulator-manager.py deps " + identifier
        )
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
        staged_git = stage_git_metadata(src, cloned)
        if identifier == "bsnes":
            run_build(["make", "-C", str(cloned / "bsnes"), "build=release",
                       "local=false", f"-j{jobs}"], work, log)
        else:
            args = ["cmake", "-S", str(cloned), "-B", str(work / "build"),
                    "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"]
            if identifier == "melonds":
                args.append("-DCMAKE_INSTALL_PREFIX=/usr")
            if identifier == "kytyps5":
                args.extend(["-DCMAKE_C_COMPILER=clang", "-DCMAKE_CXX_COMPILER=clang++"])
            run_build(args, work, log)
            command = ["cmake", "--build", str(work / "build"), "--parallel", str(jobs)]
            if identifier == "kytyps5":
                command.extend(["--target", "launcher"])
            run_build(command, work, log)
            if identifier == "kytyps5":
                run_build(["cmake", "--install", str(work / "build"),
                           "--prefix", str(work / "package")], work, log)
        candidates = [work / p for p in RECIPES[identifier]["artifacts"]]
        binary = next((p for p in candidates if p.is_file() and not p.is_symlink()), None)
        if binary is None:
            raise ManagerError(f"Expected executable not produced; inspect {log.relative_to(ROOT)}")
        if binary.stat().st_size == 0:
            raise ManagerError("Build produced an empty binary")
        package, executable = _build_package(identifier, work, cloned, binary)
        return install_build_bundle(identifier, package, executable, {
            "method": "pinned-source-build", "source": pin["url"],
            "commit": pin["commit"], "build_log": str(log.relative_to(ROOT)),
            "host": {"os": platform.system(), "architecture": platform.machine(),
                     "python": platform.python_version()},
            "toolchain": toolchain_info(),
            "staging": staged_git,
            "warning": "Binary existence is not proof of runtime compatibility; resources may still be required.",
        })


def _bundle_tree_hash(folder: Path) -> tuple[str, list[dict]]:
    """Hash exactly the packaged regular files. Refuse links/devices and path escapes."""
    items = []
    total_size = 0
    if not folder.is_dir() or folder.is_symlink():
        raise ManagerError("Bundle root must be a plain directory")
    for base, directories, files in os.walk(folder, followlinks=False):
        current = Path(base)
        for name in directories + files:
            child = current / name
            if child.is_symlink():
                raise ManagerError("Bundle contains unsupported symlink: " + str(child))
            if not child.is_dir() and not child.is_file():
                raise ManagerError("Bundle contains nonregular file: " + str(child))
        for filename in sorted(files):
            path = current / filename
            relative = path.relative_to(folder).as_posix()
            size = path.stat().st_size
            total_size += size
            if total_size > 2_500_000_000:
                raise ManagerError("Bundle exceeds 2.5 GB size limit")
            items.append({"path": relative, "sha256": hash_file(path), "size": size})
            if len(items) > 20000:
                raise ManagerError("Bundle exceeds 20,000 file limit")
    items.sort(key=lambda x: x["path"])
    canonical = json.dumps(items, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), items


def _build_package(identifier: str, work: Path, source: Path, binary: Path) -> tuple[Path, str]:
    """Stage a complete runtime payload in the disposable build root."""
    folder = work / "package-ready"
    folder.mkdir()
    executable = RECIPES[identifier]["name"]
    if identifier == "kytyps5":
        # Upstream cmake --install deploys updater, libQt6*, plugins and qt.conf.
        installed = work / "package"
        if not installed.is_dir():
            raise ManagerError("KytyPS5 did not create its installed Qt/runtime package")
        shutil.copytree(installed, folder, dirs_exist_ok=True)
        # Upstream's Linux installer may omit its helper target even though
        # launcher depends on it. The helper is needed for game execution.
        if not (folder / "kyty_emulator").is_file():
            candidates = [
                path for path in (work / "build").rglob("kyty_emulator")
                if path.is_file() and not path.is_symlink()
            ]
            if len(candidates) != 1:
                raise ManagerError("Expected exactly one kyty_emulator runtime helper; "
                                   "refusing incomplete launcher bundle")
            shutil.copy2(candidates[0], folder / "kyty_emulator")
    else:
        shutil.copy2(binary, folder / executable)
        if identifier == "ppsspp":
            resources = source / "assets"
            if not resources.is_dir():
                raise ManagerError("PPSSPP assets missing from pinned source")
            shutil.copytree(resources, folder / "assets")
        elif identifier == "bsnes":
            # Official Linux builds need shader presets and database files at runtime.
            shaders = source / "shaders"
            database = source / "bsnes" / "Database"
            if not shaders.is_dir() or not database.is_dir():
                raise ManagerError("bsnes shaders or game database missing")
            shutil.copytree(shaders, folder / "shaders")
            shutil.copytree(database, folder / "Database")
    candidate = folder / executable
    if not candidate.is_file() or candidate.is_symlink() or candidate.stat().st_size == 0:
        raise ManagerError("Expected package entrypoint was not produced: " + executable)
    if not os.access(candidate, os.X_OK):
        candidate.chmod(0o755)
    return folder, executable


def install_build_bundle(identifier: str, package: Path, binary_name: str, origin: dict) -> dict:
    """Promote immutable runtime payload before atomically switching a launcher.

    Every prior launcher references a unique content-addressed payload, so the
    existing binary rollback mechanism restores its matching resources as well.
    """
    dest = destination(identifier, binary_name)
    bundle_hash, entries = _bundle_tree_hash(package)
    if not entries:
        raise ManagerError("Cannot install empty runtime bundle")
    bundle_id = bundle_hash[:32]
    store = dest.parent / ".emustack-bundles"
    ensure_dir(store)
    target = store / bundle_id
    check_managed_path(target)
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_dir():
            raise ManagerError("Bundle destination is not an ordinary directory")
        existing_hash, _ = _bundle_tree_hash(target)
        if existing_hash != bundle_hash:
            raise ManagerError("Existing versioned bundle changed unexpectedly; refusing to overwrite")
    else:
        staging = Path(tempfile.mkdtemp(prefix=".emustack-stage-", dir=store))
        try:
            shutil.copytree(package, staging, dirs_exist_ok=True)
            after_hash, _ = _bundle_tree_hash(staging)
            if after_hash != bundle_hash:
                raise ManagerError("Bundle payload changed while copying")
            staging.rename(target)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    # Runtime paths refer to only this console's RO /custom-emulators mount.
    entry = shlex.quote("./" + binary_name)
    runtime_dir = "/custom-emulators/.emustack-bundles/" + bundle_id
    launcher = (
        "#!/bin/sh\n"
        "# EmuStack managed launcher: immutable versioned runtime package\n"
        "cd " + shlex.quote(runtime_dir) + " || exit 126\n"
        "exec " + entry + ' "$@"\n'
    )
    temp = STATE / "work" / (identifier + "-launcher-" + bundle_id + ".sh")
    ensure_dir(temp.parent)
    if temp.exists() or temp.is_symlink():
        raise ManagerError("Staged launcher already exists")
    try:
        temp.write_text(launcher, encoding="utf-8")
        temp.chmod(0o700)
        result = install_artifact(identifier, temp, binary_name, {
            **origin, "method": "pinned-source-build-bundle",
            "bundle_id": bundle_id, "bundle_sha256": bundle_hash,
            "bundle_files": len(entries), "bundle_entrypoint": binary_name,
            "bundle_directory": str(target.relative_to(ROOT)),
        }, hash_file(temp))
        return {**result, "bundle_files": len(entries),
                "bundle_sha256": bundle_hash,
                "bundle_directory": str(target.relative_to(ROOT))}
    finally:
        temp.unlink(missing_ok=True)


def verify_bundle(identifier: str, current: dict) -> bool | None:
    info = current.get("origin", {})
    expected = info.get("bundle_sha256")
    bundle_id = info.get("bundle_id")
    if not expected:
        return None
    if not HEX64.fullmatch(expected) or not isinstance(bundle_id, str):
        return False
    if bundle_id != expected[:32]:
        return False
    root = ROOT / "data" / "environments" / identifier / "emulators" / ".emustack-bundles" / bundle_id
    try:
        check_managed_path(root)
        if root.is_symlink():
            return False
        actual, _ = _bundle_tree_hash(root)
        return actual == expected
    except (ManagerError, OSError):
        return False




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

        archived = file.with_suffix(".json")
        record = load_json(archived) if archived.is_file() and not archived.is_symlink() else None
        records.append({"file": file.name, "sha256": sha, "size": file.stat().st_size,
                        "origin": record.get("origin") if record else None})
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

    provenance = versions[0].get("origin")
    if provenance and provenance.get("bundle_sha256"):
        # The saved launcher contains a permanent content-addressed bundle path.
        # Refuse rollback if the resources of that version have been corrupted.
        if not verify_bundle(identifier, {"origin": provenance}):
            raise ManagerError("Previous bundle payload missing or corrupted; rollback refused")
    return install_artifact(identifier, candidate, record["binary_name"],
                            {**(provenance or {}), "restored_from": versions[0]["file"],
                             "method": "rollback"},
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
            "bundle_hash_valid": verify_bundle(name, current) if current else None,
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
    plan = sub.add_parser("plan-deps", help="show first-level pinned nested sources and origins; no network")
    plan.add_argument("id", choices=sorted(RECIPES))
    sync = sub.add_parser("sync-deps", help="audit and download index-pinned nested source checkouts")
    sync.add_argument("id", choices=sorted(RECIPES))
    sync.add_argument("--jobs", type=int, default=2)
    sync.add_argument("--yes-download-submodules", action="store_true")
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
        elif args.action == "plan-deps":
            data = plan_deps(args.id)
        elif args.action == "sync-deps":
            data = sync_deps(args.id, args.jobs, args.yes_download_submodules)
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
