#!/usr/bin/env bash
# Confirm three separately built images and their package/report boundaries.
set -Eeuo pipefail

probe='import json, shutil, sys
expected = sys.argv[1]
commands = {"dolphin": "dolphin-emu", "mupen64plus": "mupen64plus-ui-console"}
with open("/opt/emustack/install-report.json", encoding="utf-8") as f:
    items = json.load(f)["items"]
assert isinstance(items, dict) and len(items) == 20, "20-entry install report required"
for name, command in commands.items():
    executable = shutil.which(command)
    if name == expected:
        assert executable, f"{name} missing in {expected} image"
        assert items[name]["status"] == "installed", f"{name}: {items[name]}"
    else:
        assert not executable, f"{name} leaked to {expected}: {executable}"
if expected == "common":
    assert items["dolphin"]["status"] == "profile-image-only", items["dolphin"]
print(f"Profile package isolation and metadata PASS: {expected}")'

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
