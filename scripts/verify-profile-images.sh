#!/usr/bin/env bash
# Confirm three separately built images and their package/report boundaries.
set -Eeuo pipefail

probe='import json, shutil, sys
expected = sys.argv[1]
commands = {"dolphin": ("dolphin-emu",), "mupen64plus": ("mupen64plus-ui-console", "mupen64plus")}
with open("/opt/emustack/install-report.json", encoding="utf-8") as f:
    items = json.load(f)["items"]
assert isinstance(items, dict) and len(items) == 20, "20-entry install report required"
for name, candidates in commands.items():
    executables = {cmd: shutil.which(cmd) for cmd in candidates}
    installed = {cmd: path for cmd, path in executables.items() if path}
    if name == expected:
        assert installed, f"{name} missing in {expected} image; tested: {candidates}"
        assert items[name]["status"] == "installed", f"{name}: {items[name]}"
    else:
        assert not installed, f"{name} leaked into {expected}: {installed}"
if expected == "common":
    assert items["dolphin"]["status"] == "profile-image-only", items["dolphin"]
# PATH-only checks miss packages that install shared libraries but no executable.
# Query dpkg directly so an accidental APT regression cannot silently contaminate
# the common runtime (or leak Mupen dependencies into Dolphin and vice versa).
import subprocess
def package_installed(name):
    process = subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}", name],
        capture_output=True, text=True, check=False,
    )
    return process.returncode == 0 and process.stdout.strip() == "install ok installed"

packages = {
    "dolphin": "dolphin-emu",
    "mupen64plus": "mupen64plus-ui-console",
    "mupen_gdcm": "libgdcm3.0t64",
    "mupen_mariadb": "libmariadb3",
    "dolphin_stb": "libstb0t64",
}
observed = {name: package_installed(pkg) for name, pkg in packages.items()}
if expected == "common":
    assert not any(observed.values()), f"Unexpected Dolphin/Mupen APT dependency in common image: {observed}"
elif expected == "dolphin":
    assert observed["dolphin"] and observed["dolphin_stb"], f"Dolphin APT dependencies missing: {observed}"
    assert not observed["mupen64plus"] and not observed["mupen_gdcm"] and not observed["mupen_mariadb"], (
        f"Mupen APT dependencies leaked into Dolphin: {observed}"
    )
elif expected == "mupen64plus":
    assert observed["mupen64plus"] and observed["mupen_gdcm"] and observed["mupen_mariadb"], (
        f"Mupen APT dependencies missing: {observed}"
    )
    assert not observed["dolphin"] and not observed["dolphin_stb"], (
        f"Dolphin APT dependencies leaked into Mupen: {observed}"
    )
print(f"Profile package isolation and metadata PASS: {expected}; dpkg={observed}")'

for item in   "common:local/emustack:0.7.1"   "dolphin:local/emustack-dolphin:0.7.1"   "mupen64plus:local/emustack-mupen64plus:0.7.1"; do
  profile="${item%%:*}"
  image="${item#*:}"
  docker run --rm --network none --entrypoint python3 "$image" -c "$probe" "$profile"
done

a="$(docker image inspect --format '{{.Id}}' local/emustack:0.7.1)"
b="$(docker image inspect --format '{{.Id}}' local/emustack-dolphin:0.7.1)"
c="$(docker image inspect --format '{{.Id}}' local/emustack-mupen64plus:0.7.1)"
[[ "$a" != "$b" && "$a" != "$c" && "$b" != "$c" ]] || {
  echo "ERROR: profile images did not receive distinct image IDs" >&2
  exit 1
}
echo "Three independent Docker image IDs verified."
