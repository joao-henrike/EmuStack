#!/usr/bin/env bash
# Explicit build in a nonprivileged Trixie container. Not used by Compose.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
usage() {
  echo "Usage: bash scripts/build-phase1-isolated.sh {kytyps5|shadps4|ppsspp|melonds} --yes-run-upstream-code [--jobs 1..4]" >&2
  exit 2
}
[[ $# -ge 2 ]] || usage
id="$1"
case "$id" in kytyps5|shadps4|ppsspp|melonds) ;; *) usage ;; esac
[[ "$2" == "--yes-run-upstream-code" ]] || usage
shift 2
jobs=2
if [[ $# -gt 0 ]]; then
  [[ "$1" == "--jobs" && $# -eq 2 ]] || usage
  jobs="$2"
  [[ "$jobs" =~ ^[1-4]$ ]] || usage
fi
[[ "$(id -u)" -ne 0 ]] || { echo "ERRO: não execute com sudo/root." >&2; exit 1; }
command -v docker >/dev/null || { echo "ERRO: Docker CLI ausente." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "ERRO: Docker daemon indisponível." >&2; exit 1; }
[[ -d "$ROOT/.git" || -f "$ROOT/.git" ]] || { echo "ERRO: exige um checkout Git do EmuStack." >&2; exit 1; }
[[ ! -L "$ROOT/data" ]] || { echo "ERRO: data/ não pode ser symlink." >&2; exit 1; }
mkdir -p "$ROOT/data"
data_real="$(realpath -- "$ROOT/data")"
[[ "$data_real" == "$ROOT/data" ]] || { echo "ERRO: data/ resolve fora do projeto." >&2; exit 1; }
tag="emustack-phase1-builder:trixie"
echo "== Construindo toolchain isolada (sem alterar APT do host) =="
docker build --file "$ROOT/scripts/phase1-builder/Dockerfile" \
  --tag "$tag" "$ROOT/scripts/phase1-builder"
echo "== Compilando $id (UID $(id -u), fonte read-only) =="
docker run --rm --init \
  --user "$(id -u):$(id -g)" \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 512 --cpus 4 --memory 8g \
  --network bridge --ipc private \
  --mount "type=bind,src=$ROOT,dst=/workspace,readonly" \
  --mount "type=bind,src=$data_real,dst=/workspace/data" \
  --env HOME=/tmp --env XDG_CACHE_HOME=/tmp/.cache \
  --env GIT_OPTIONAL_LOCKS=0 \
  --workdir /workspace \
  "$tag" python3 scripts/emulator-manager.py build "$id" \
  --jobs "$jobs" --yes-run-upstream-code
echo "== Verificando o estado do binário =="
python3 scripts/emulator-manager.py status "$id"
