#!/usr/bin/env python3
"""Audited, explicit management of EmuStack's pinned emulator source submodules.

No upstream source is executed by this utility. Source refs and URLs are allowlisted
in upstream/source-lock.json and .gitmodules. Binary installations still use the
independent release-lock.json until a per-emulator source-build migration is tested.
"""
from __future__ import annotations

import argparse
import configparser
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "upstream" / "source-lock.json"
GITMODULES = ROOT / ".gitmodules"
SHA = re.compile(r"^[a-f0-9]{40}$")
COMPONENT = re.compile(r"^[a-z][a-z0-9-]*$")
EXPECTED_PROFILES = {
    "kytyps5", "shadps4", "rpcs3", "duckstation", "pcsx2", "ppsspp",
    "vita3k", "xbox-one", "xenia-canary", "xbox-series", "xemu", "eden",
    "cemu", "dolphin", "azahar", "melonds", "mgba", "mupen64plus",
    "bsnes", "mesen",
}


EXPECTED_REMOTES = {
    "kytyps5": "https://github.com/KytyPS5/KytyPS5.git",
    "shadps4": "https://github.com/shadps4-emu/shadPS4.git",
    "rpcs3": "https://github.com/RPCS3/rpcs3.git",
    "duckstation": "https://github.com/stenzek/duckstation.git",
    "pcsx2": "https://github.com/PCSX2/pcsx2.git",
    "ppsspp": "https://github.com/hrydgard/ppsspp.git",
    "vita3k": "https://github.com/Vita3K/Vita3K.git",
    "xenia-canary": "https://github.com/xenia-canary/xenia-canary.git",
    "xemu": "https://github.com/xemu-project/xemu.git",
    "cemu": "https://github.com/cemu-project/Cemu.git",
    "dolphin": "https://github.com/dolphin-emu/dolphin.git",
    "azahar": "https://github.com/azahar-emu/azahar.git",
    "melonds": "https://github.com/melonDS-emu/melonDS.git",
    "mgba": "https://github.com/mgba-emu/mgba.git",
    "bsnes": "https://github.com/bsnes-emu/bsnes.git",
    "mesen": "https://github.com/SourMesen/Mesen2.git",
    "mupen64plus-core": "https://github.com/mupen64plus/mupen64plus-core.git",
    "mupen64plus-ui-console": "https://github.com/mupen64plus/mupen64plus-ui-console.git",
    "mupen64plus-audio-sdl": "https://github.com/mupen64plus/mupen64plus-audio-sdl.git",
    "mupen64plus-input-sdl": "https://github.com/mupen64plus/mupen64plus-input-sdl.git",
    "mupen64plus-rsp-hle": "https://github.com/mupen64plus/mupen64plus-rsp-hle.git",
    "mupen64plus-video-rice": "https://github.com/mupen64plus/mupen64plus-video-rice.git",
    "mupen64plus-video-glide64mk2": "https://github.com/mupen64plus/mupen64plus-video-glide64mk2.git",
    "eden": "https://git.eden-emu.dev/eden-emu/eden.git",
}



def git(*args: str, cwd: Path = ROOT, timeout: int = 180) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, check=False, timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip()
                           or f"Git command failed: {args[0]}")
    return result.stdout.strip()


def validate() -> tuple[dict, list[dict]]:
    payload = json.loads(LOCK.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("strategy") != "pinned-git-submodules":
        raise ValueError("Unsupported or invalid source-lock schema")
    sources = payload.get("sources")
    profiles = payload.get("profiles")
    if not isinstance(sources, list) or not isinstance(profiles, list):
        raise ValueError("Source lock requires source and profile arrays")
    by_profile = {p["id"]: p for p in profiles}
    if set(by_profile) != EXPECTED_PROFILES or len(profiles) != 20:
        raise ValueError("Source lock must cover all 20 unique profiles")

    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(GITMODULES, encoding="utf-8")
    if len(cfg.sections()) != len(sources):
        raise ValueError("Number of .gitmodules entries differs from the lock")

    ids = set()
    for source in sources:
        identifier = source["id"]
        path = source["path"]
        url = source["url"]
        branch = source["branch"]
        commit = source["commit"]
        if not COMPONENT.fullmatch(identifier) or identifier in ids:
            raise ValueError(f"Invalid or duplicate source ID: {identifier}")
        ids.add(identifier)
        if path != f"third_party/{identifier}" or source["profile"] not in by_profile:
            raise ValueError(f"Invalid source path/profile: {identifier}")
        if not SHA.fullmatch(commit):
            raise ValueError(f"Invalid 40-hex SHA: {identifier}")
        if url != EXPECTED_REMOTES.get(identifier):
            raise ValueError(f"Unknown or changed official origin: {identifier}")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.username or parsed.password or
                parsed.port or parsed.query or parsed.fragment or
                parsed.hostname not in {"github.com", "git.eden-emu.dev"} or
                not parsed.path.endswith(".git") or
                not all(x and x not in {".", ".."} for x in parsed.path.strip("/").split("/"))):
            raise ValueError(f"Non-allowlisted Git source: {identifier}")
        if parsed.hostname == "git.eden-emu.dev" and url != "https://git.eden-emu.dev/eden-emu/eden.git":
            raise ValueError("Forgejo host only allowed for the official Eden repository")
        if not re.fullmatch(r"[A-Za-z0-9._/-]{1,120}", branch) or ".." in branch or branch.startswith("/"):
            raise ValueError(f"Invalid branch: {identifier}")
        section = f'submodule "{path}"'
        if not cfg.has_section(section):
            raise ValueError(f"Missing .gitmodules section: {path}")
        for key, expected in {"path": path, "url": url, "branch": branch}.items():
            if cfg.get(section, key, fallback=None) != expected:
                raise ValueError(f".gitmodules mismatch: {path}.{key}")

    if ids != set(EXPECTED_REMOTES):
        raise ValueError("Official upstream source allowlist differs from the lock")

    for profile in profiles:
        expected = [s["id"] for s in sources if s["profile"] == profile["id"]]
        if profile.get("components") != expected:
            raise ValueError(f"Profile component mapping does not match: {profile['id']}")
        if profile["id"] in {"xbox-one", "xbox-series"}:
            if profile.get("state") != "unsupported-no-source" or expected:
                raise ValueError("Unsupported console profiles must not claim source runners")
        elif profile.get("state") != "source-pinned" or not expected:
            raise ValueError(f"Emulator profile has no pinned source: {profile['id']}")
    if len(sources) != 24:
        raise ValueError(f"Expected 24 source modules, found {len(sources)}")
    return payload, sources


def check_index(sources: list[dict]) -> None:
    for source in sources:
        path = source["path"]
        entry = git("ls-files", "--stage", "--", path)
        expected = f"160000 {source['commit']} 0\t{path}"
        if entry != expected:
            raise ValueError(f"Git index gitlink mismatch for {path}: {entry!r}")


def checkout_state(source: dict) -> str:
    path = ROOT / source["path"]
    if not (path / ".git").exists():
        return "not-fetched"
    try:
        head = git("rev-parse", "HEAD", cwd=path)
        dirty = bool(git("status", "--porcelain", cwd=path))
    except (RuntimeError, OSError):
        return "invalid-checkout"
    if head != source["commit"]:
        return "wrong-commit"
    return "dirty" if dirty else "ok"


def status(require_checkout: bool = False) -> None:
    _, sources = validate()
    check_index(sources)
    failures = []
    for s in sources:
        state = checkout_state(s)
        print(f"{s['profile']:14} {s['id']:32} {state:16} {s['commit'][:12]}")
        if state not in ("ok", "not-fetched") or (require_checkout and state != "ok"):
            failures.append(s["id"])
    print(f"Source lock: 20 profiles / {len(sources)} gitlinks; "
          f"checkouts {'required' if require_checkout else 'optional'}")
    if failures:
        raise RuntimeError(f"Invalid/unsynced source checkouts: {', '.join(failures)}")


def sync(jobs: int) -> None:
    _, sources = validate()
    check_index(sources)
    if jobs < 1 or jobs > 8:
        raise ValueError("--jobs must be 1..8")
    paths = [s["path"] for s in sources]
    git("submodule", "sync", "--", *paths)
    git("-c", "protocol.file.allow=never", "submodule", "update", "--init",
        f"--jobs={jobs}", "--", *paths, timeout=7200)
    status(require_checkout=True)


def plan(identifier: str | None) -> None:
    _, sources = validate()
    check_index(sources)
    selected = [s for s in sources if identifier is None or s["id"] == identifier]
    if not selected:
        raise ValueError(f"Unknown component: {identifier}")
    for s in selected:
        remote = git("ls-remote", "--refs", s["url"],
                     f"refs/heads/{s['branch']}", timeout=60)
        rows = [line.split() for line in remote.splitlines() if line.strip()]
        if len(rows) != 1 or len(rows[0]) != 2 or not SHA.fullmatch(rows[0][0]):
            raise RuntimeError(f"Unable to resolve the official branch: {s['id']}")
        remote_sha = rows[0][0]
        state = "up-to-date" if remote_sha == s["commit"] else "candidate"
        print(f"{s['id']:32} {state:12} pinned={s['commit']} remote={remote_sha}")
    print("No pins changed. Review upstream source, license, dependencies, and tests before updating.")


def pin(identifier: str, commit: str) -> None:
    payload, sources = validate()
    check_index(sources)
    target = next((s for s in sources if s["id"] == identifier), None)
    if target is None or not SHA.fullmatch(commit):
        raise ValueError("Provide a known component ID and exact 40-hex commit")
    current_branch = git("branch", "--show-current")
    if not current_branch or current_branch in {"main", "master"}:
        raise ValueError("Pin updates require a dedicated non-default review branch")
    if git("status", "--porcelain", "--", target["path"], str(LOCK.relative_to(ROOT))):
        raise ValueError("Submodule pin/index already has uncommitted changes")
    path = ROOT / target["path"]
    if checkout_state(target) != "ok":
        raise ValueError("Initialize and clean the submodule before changing its pin")
    git("fetch", "--no-tags", "--", target["url"], commit, cwd=path, timeout=900)
    if git("cat-file", "-t", commit, cwd=path) != "commit":
        raise ValueError("The fetched hash is not a commit")
    git("checkout", "--detach", commit, cwd=path)
    target["commit"] = commit
    LOCK.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    git("add", "--", target["path"], str(LOCK.relative_to(ROOT)))
    check_index(sources)
    print(f"Staged {identifier}@{commit}. Run audit/tests; create a review PR; do not auto-merge.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    audit = subs.add_parser("audit", help="verify official source metadata and indexed gitlinks")
    audit.add_argument("--require-checkout", action="store_true")
    sync_parser = subs.add_parser("sync", help="initialize all 24 pinned submodules in one batch")
    sync_parser.add_argument("--jobs", type=int, default=4)
    plan_parser = subs.add_parser("plan", help="read current upstream branch tips without changing pins")
    plan_parser.add_argument("--id", dest="identifier", help="only inspect one component ID")
    pin_parser = subs.add_parser("pin", help="stage a reviewed source commit in a non-default branch")
    pin_parser.add_argument("identifier")
    pin_parser.add_argument("commit")
    args = parser.parse_args()
    try:
        if args.action == "audit":
            status(require_checkout=args.require_checkout)
        elif args.action == "sync":
            sync(args.jobs)
        elif args.action == "plan":
            plan(args.identifier)
        elif args.action == "pin":
            pin(args.identifier, args.commit)
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"UPSTREAM MANAGER ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
