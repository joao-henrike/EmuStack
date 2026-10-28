#!/usr/bin/env bash
# Build once with the existing policy, pin successful upstream assets by SHA-256,
# then rebuild using the strict lock. The base-image digest is pinned; use APT_SNAPSHOT_TIMESTAMP to freeze the Debian package repository too.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v docker >/dev/null 2>&1 || { echo 'ERROR: Docker CLI is required.' >&2; exit 127; }
docker compose version >/dev/null 2>&1 || { echo 'ERROR: Docker Compose v2 is required.' >&2; exit 127; }
docker info >/dev/null 2>&1 || { echo 'ERROR: Docker daemon is unavailable.' >&2; exit 1; }
compose=(docker compose -f compose.yaml)
[[ ! -f compose.override.yaml ]] || compose+=(-f compose.override.yaml)
if [[ "${USE_NVIDIA:-0}" == "1" ]]; then compose+=(-f compose.nvidia.yaml); fi
lock_tmp="$(mktemp "${ROOT}/release-lock.json.new.XXXXXX")"
old_tmp="$(mktemp "${ROOT}/release-lock.json.old.XXXXXX")"
cleanup() { rm -f "$lock_tmp" "$old_tmp"; }
trap cleanup EXIT HUP INT TERM
cp release-lock.json "$old_tmp"
printf '\n== Build current permissive/previously locked image ==\n'
"${compose[@]}" build --progress=plain
printf '\n== Export checksummed official release assets ==\n'
"${compose[@]}" run --rm --no-deps emustack export-lock > "$lock_tmp"
python3 scripts/check-release-lock.py "$lock_tmp" --require-strict --require-pins
mv "$lock_tmp" release-lock.json
if ! "${compose[@]}" build --progress=plain; then
  cp "$old_tmp" release-lock.json
  echo 'ERROR: strict rebuild failed; previous release-lock.json restored.' >&2
  exit 1
fi
python3 scripts/check-release-lock.py release-lock.json --require-strict
printf '\n== Final install report under strict lock ==\n'
"${compose[@]}" run --rm emustack install-report
printf '\nLock frozen and image rebuilt. The base-image digest is pinned. For reproducible APT package resolution, invoke with APT_SNAPSHOT_TIMESTAMP=YYYYMMDDTHHMMSSZ; note this also freezes security updates at that time.\n'
