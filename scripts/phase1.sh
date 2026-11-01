#!/usr/bin/env bash
# EmuStack Phase 1: build, inspect and test IN Docker. No host-side build toolchain.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
cd "$ROOT"

usage() {
  cat >&2 <<'USAGE'
Usage:
  bash scripts/phase1.sh status [profile-id]
  bash scripts/phase1.sh deps {kytyps5|shadps4|ppsspp|melonds|bsnes}
  bash scripts/phase1.sh test
  bash scripts/phase1.sh build {kytyps5|shadps4|ppsspp|melonds|bsnes} --yes-run-upstream-code [--jobs 1..4]

Builds run upstream code inside a nonprivileged Debian Trixie container.
Only project data/ is writable; the checkout, source lock and Git objects are read-only.
No host APT/CMake/Qt/SDL/Python or Docker socket inside the build container.
USAGE
  exit 2
}
[[ $# -ge 1 ]] || usage
action="$1"
shift
case "$action" in status|deps|test|build) ;; *) usage ;; esac

valid_id() {
  case "$1" in kytyps5|shadps4|ppsspp|melonds|bsnes) return 0 ;; *) return 1 ;; esac
}

jobs=2
id=""
case "$action" in
  test) [[ $# -eq 0 ]] || usage ;;
  status)
    [[ $# -le 1 ]] || usage
    if [[ $# -eq 1 ]]; then
      case "$1" in
        kytyps5|shadps4|ppsspp|melonds|bsnes|rpcs3|duckstation|pcsx2|vita3k|xbox-one|xenia-canary|xbox-series|xemu|eden|cemu|dolphin|azahar|mgba|mupen64plus|mesen) ;;
        *) usage ;;
      esac
      id="$1"
    fi
    ;;
  deps)
    [[ $# -eq 1 ]] || usage
    valid_id "$1" || usage
    id="$1"
    ;;
  build)
    [[ $# -ge 2 ]] || usage
    valid_id "$1" || usage
    id="$1"
    [[ "$2" == "--yes-run-upstream-code" ]] || usage
    shift 2
    if [[ $# -gt 0 ]]; then
      [[ $# -eq 2 && "$1" == "--jobs" && "$2" =~ ^[1-4]$ ]] || usage
      jobs="$2"
    fi
    ;;
esac

[[ "$(id -u)" -ne 0 ]] || { echo "ERRO: não execute como root/sudo." >&2; exit 1; }
command -v docker >/dev/null || { echo "ERRO: precisa de Docker CLI no host." >&2; exit 127; }
docker info >/dev/null 2>&1 || { echo "ERRO: daemon Docker indisponível ou sem permissão." >&2; exit 1; }
[[ -d "$ROOT/.git" || -f "$ROOT/.git" ]] || { echo "ERRO: exige checkout Git do EmuStack." >&2; exit 1; }

# data is the only writable host bind. Reject symlinks and unexpected relocations.
[[ ! -L "$ROOT/data" ]] || { echo "ERRO: data/ não pode ser symlink." >&2; exit 1; }
mkdir -p "$ROOT/data"
[[ "$(realpath -e -- "$ROOT/data")" == "$ROOT/data" ]] || {
  echo "ERRO: data/ fora da raiz do projeto." >&2; exit 1;
}
tag="local/emustack-phase1-builder:trixie"
docker build --file "$ROOT/scripts/phase1-builder/Dockerfile" \
  --tag "$tag" "$ROOT/scripts/phase1-builder"

network=none
[[ "$action" == "build" ]] && network=bridge
docker_args=(
  run --rm --init
  --user "$(id -u):$(id -g)"
  --read-only
  --tmpfs /tmp:rw,nosuid,nodev,size=2g
  --cap-drop ALL
  --security-opt no-new-privileges
  --pids-limit 512
  --cpus 4
  --memory 8g
  --network "$network"
  --ipc private
  --mount "type=bind,src=$ROOT,dst=/workspace,readonly"
  --mount "type=bind,src=$ROOT/data,dst=/workspace/data"
  --env HOME=/tmp
  --env XDG_CACHE_HOME=/tmp/.cache
  --env GIT_OPTIONAL_LOCKS=0
  --workdir /workspace
  "$tag"
)

case "$action" in
  build)
    echo "== BUILD ISOLADO: $id (fontes pinadas; rede temporária de build) =="
    docker "${docker_args[@]}" python3 scripts/emulator-manager.py \
      build "$id" --jobs "$jobs" --yes-run-upstream-code
    ;;
  deps|status)
    if [[ -n "$id" ]]; then
      docker "${docker_args[@]}" python3 scripts/emulator-manager.py "$action" "$id"
    else
      docker "${docker_args[@]}" python3 scripts/emulator-manager.py "$action"
    fi
    ;;
  test)
    docker "${docker_args[@]}" python3 -m unittest discover \
      -s tests -p 'test_emulator_manager.py' -v
    ;;
esac
