#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "ERROR: this acceptance test must run on the target host with a working Docker daemon." >&2
  exit 127
fi
if [[ ! -f .env ]]; then
  echo "ERROR: .env is missing; run ./scripts/host-setup.sh first." >&2
  exit 1
fi
python3 scripts/runtime-acceptance.py
