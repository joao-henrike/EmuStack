#!/usr/bin/env python3
"""Show bounded local compilation log, never execute upstream build output."""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "data" / "emulator-manager" / "logs"
PROFILE_IDS = frozenset({
    "kytyps5", "shadps4", "rpcs3", "duckstation", "pcsx2", "ppsspp",
    "vita3k", "xbox-one", "xenia-canary", "xbox-series", "xemu", "eden",
    "cemu", "dolphin", "azahar", "melonds", "mgba", "mupen64plus", "bsnes", "mesen",
})

def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in PROFILE_IDS:
        print("Usage: phase1-logs.py <valid-profile-id>", file=sys.stderr)
        return 2
    profile = sys.argv[1]
    if LOG_DIR.is_symlink() or not LOG_DIR.is_dir():
        print("No managed logs available", file=sys.stderr)
        return 1
    candidates = sorted(
        (p for p in LOG_DIR.glob(profile + "-*.log")
         if p.is_file() and not p.is_symlink()),
        key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True
    )
    if not candidates:
        print("No build log for " + profile)
        return 0
    latest = candidates[0]
    print("Log: " + str(latest.relative_to(ROOT)))
    with latest.open("r", encoding="utf-8", errors="replace") as stream:
        sys.stdout.writelines(deque(stream, maxlen=120))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
