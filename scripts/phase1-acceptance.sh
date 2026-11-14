#!/usr/bin/env bash
# Phase 1 acceptance: inspect installed payloads inside actual runtime agent images.
# No games, BIOS, firmware or GUI emulators are executed.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
cd "$ROOT"
case "${1:-all}" in
  all) ids=(kytyps5 shadps4 ppsspp melonds bsnes) ;;
  kytyps5|shadps4|ppsspp|melonds|bsnes) ids=("$1") ;;
  *) echo "Usage: $0 [all|kytyps5|shadps4|ppsspp|melonds|bsnes]" >&2; exit 2 ;;
esac
command -v docker >/dev/null || { echo "Docker CLI required" >&2; exit 127; }
docker compose version >/dev/null || { echo "Docker Compose v2 required" >&2; exit 127; }
docker compose -f compose.yaml config --quiet
failed=0
for id in "${ids[@]}"; do
  printf '\n=== PHASE 1 PACKAGE: %s ===\n' "$id"
  if ! docker compose -f compose.yaml run --rm --no-deps \
      --entrypoint python3 "env-$id" \
      /opt/emustack/scripts/phase1-smoke.py "$id"; then
    echo "FAIL: $id; inspect runtime output/build logs" >&2
    failed=1
  fi
done
exit "$failed"
