#!/usr/bin/env python3
"""Read-only in-container diagnostic for a built, packaged emulator."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/custom-emulators")
ALLOWED = {
    "kytyps5": "kyty_launcher", "shadps4": "shadPS4",
    "ppsspp": "PPSSPPSDL", "melonds": "melonDS", "bsnes": "bsnes",
}

def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ALLOWED:
        print("Usage: phase1-smoke.py <profile>", file=sys.stderr)
        return 2
    profile = sys.argv[1]
    entry = ROOT / ALLOWED[profile]
    report = {"id": profile, "wrapper_present": entry.is_file(),
              "runtime_execution_tested": False}
    if not entry.is_file() or entry.is_symlink() or not os.access(entry, os.X_OK):
        report["error"] = "managed executable missing, symlinked or not executable"
        print(json.dumps(report, indent=2))
        return 1
    first = entry.read_bytes()[:8192]
    marker = b"/custom-emulators/.emustack-bundles/"
    if marker not in first:
        report["warning"] = "legacy unmanaged/raw binary; bundle identity unavailable"
        print(json.dumps(report, indent=2))
        return 0
    text = first.decode("utf-8", errors="replace")
    import re
    found = re.search(r"^cd /custom-emulators/\.emustack-bundles/([a-f0-9]{32}) \|\| exit 126$", text, re.M)
    if not found:
        report["error"] = "unexpected managed launcher structure"
        print(json.dumps(report, indent=2))
        return 1
    bundle = ROOT / ".emustack-bundles" / found.group(1)
    binary = bundle / ALLOWED[profile]
    report["bundle_found"] = bundle.is_dir() and not bundle.is_symlink()
    report["binary_found"] = binary.is_file() and not binary.is_symlink()
    report["binary_executable"] = report["binary_found"] and os.access(binary, os.X_OK)
    if not report["binary_executable"]:
        print(json.dumps(report, indent=2))
        return 1
    if profile == "ppsspp":
        report["assets_found"] = (bundle / "assets").is_dir()
    elif profile == "bsnes":
        report["assets_found"] = (bundle / "Database").is_dir() and (bundle / "shaders").is_dir()
    elif profile == "kytyps5":
        report["assets_found"] = (bundle / "qt.conf").is_file() and (bundle / "plugins").is_dir()
    else:
        report["assets_found"] = True
    if not shutil.which("ldd"):
        report["ldd"] = "not-available"
    else:
        result = subprocess.run(["ldd", str(binary)], capture_output=True, text=True,
                                timeout=30, check=False)
        report["ldd_exit_code"] = result.returncode
        report["missing_libraries"] = [
            line.strip()[:250] for line in result.stdout.splitlines()
            if " => not found" in line
        ]
    print(json.dumps(report, indent=2))
    return 0 if report["assets_found"] and not report.get("missing_libraries") and report.get("ldd_exit_code", 0) == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
