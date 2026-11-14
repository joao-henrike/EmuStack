#!/usr/bin/env bash
# Generate independent Syft SPDX / Trivy JSON reports for each runtime image.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ARTIFACTS="${EMUSTACK_SECURITY_ARTIFACTS_DIR:-$ROOT/artifacts}"
mkdir -p "$ARTIFACTS"

for item in \
  "common:local/emustack:0.7.1" \
  "dolphin:local/emustack-dolphin:0.7.1" \
  "mupen64plus:local/emustack-mupen64plus:0.7.1"; do
  name="${item%%:*}"
  image="${item#*:}"
  echo "=== Syft/Trivy for $name ($image) ==="
  EMUSTACK_SCAN_IMAGE="$image" \
    EMUSTACK_SECURITY_ARTIFACTS_DIR="$ARTIFACTS/$name" \
    bash "$ROOT/scripts/supply-chain-scan.sh"
done

python3 "$ROOT/scripts/report-image-matrix.py" --artifacts-dir "$ARTIFACTS"
