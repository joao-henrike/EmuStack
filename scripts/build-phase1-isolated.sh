#!/usr/bin/env bash
# Compatibility wrapper: all Phase 1 compilation happens inside Docker.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
exec bash "$ROOT/scripts/phase1.sh" build "$@"
