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
  bash scripts/phase1.sh test                 # focused regression tests
  bash scripts/phase1.sh validate             # full static validation
  bash scripts/phase1.sh plan-deps <profile>
  bash scripts/phase1.sh sync-deps <profile> --yes-download-submodules [--jobs 1..4]
  bash scripts/phase1.sh history <profile>
  bash scripts/phase1.sh rollback <profile>
  bash scripts/phase1.sh uninstall <profile>
  bash scripts/phase1.sh purge <profile> --yes-delete-managed-backups # irreversible
  bash scripts/phase1.sh logs <profile>
  bash scripts/phase1.sh install-file <profile> <data/imports/filename> <sha256> <allowlisted-binary-name>
  bash scripts/phase1.sh build-all --yes-run-upstream-code [--jobs 1..4]
  bash scripts/phase1.sh build {kytyps5|shadps4|ppsspp|melonds|bsnes} --yes-run-upstream-code [--jobs 1..4]

Builds run upstream code inside a nonprivileged Debian Trixie container.
Builds only write manager state and the selected profile emulators; game/BIOS/save data stays read-only.
Only explicit sync-deps may write selected upstream checkout and Git metadata.
No host APT/CMake/Qt/SDL/Python or Docker socket inside the build container.
USAGE
  exit 2
}
[[ $# -ge 1 ]] || usage
action="$1"
shift
case "$action" in status|deps|test|validate|build|build-all|plan-deps|sync-deps|history|rollback|uninstall|purge|install-file|logs) ;; *) usage ;; esac

valid_id() {
  case "$1" in kytyps5|shadps4|ppsspp|melonds|bsnes) return 0 ;; *) return 1 ;; esac
}

jobs=2
id=""
filename=""
sha=""
binary_name=""
case "$action" in
  test|validate) [[ $# -eq 0 ]] || usage ;;
  build-all)
    [[ $# -ge 1 && "$1" == "--yes-run-upstream-code" ]] || usage
    shift
    if [[ $# -gt 0 ]]; then
      [[ $# -eq 2 && "$1" == "--jobs" && "$2" =~ ^[1-4]$ ]] || usage
      jobs="$2"
    fi
    ;;
  plan-deps|sync-deps)
    [[ $# -ge 1 ]] || usage
    valid_id "$1" || usage
    id="$1"
    shift
    if [[ "$action" == "sync-deps" ]]; then
      [[ $# -ge 1 && "$1" == "--yes-download-submodules" ]] || usage
      shift
      if [[ $# -gt 0 ]]; then
        [[ $# -eq 2 && "$1" == "--jobs" && "$2" =~ ^[1-4]$ ]] || usage
        jobs="$2"
      fi
    else
      [[ $# -eq 0 ]] || usage
    fi
    ;;
  history|rollback|uninstall|logs)
    [[ $# -eq 1 ]] || usage
    id="$1"
    ;;
  purge)
    [[ $# -eq 2 && "$2" == "--yes-delete-managed-backups" ]] || usage
    id="$1"
    ;;
  install-file)
    [[ $# -eq 4 ]] || usage
    id="$1"
    filename="$2"
    sha="$3"
    binary_name="$4"
    [[ "$filename" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || usage
    [[ "$sha" =~ ^[a-f0-9]{64}$ ]] || usage
    [[ "$binary_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || usage
    ;;
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

# Commands accepting profile IDs are never forwarded unchecked to the container.
case "$action" in
  history|rollback|uninstall|purge|logs|install-file)
    case "$id" in
      kytyps5|shadps4|ppsspp|melonds|bsnes|rpcs3|duckstation|pcsx2|vita3k|xbox-one|xenia-canary|xbox-series|xemu|eden|cemu|dolphin|azahar|mgba|mupen64plus|mesen) ;;
      *) usage ;;
    esac ;;
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
if [[ "$action" == "build" || "$action" == "build-all" || "$action" == "sync-deps" ]]; then
  network=bridge
fi
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
  --mount "type=bind,src=$ROOT/data,dst=/workspace/data,readonly"
  --env HOME=/tmp
  --env XDG_CACHE_HOME=/tmp/.cache
  --env GIT_OPTIONAL_LOCKS=0
  --env PYTHONPYCACHEPREFIX=/tmp/pycache
  --workdir /workspace
)

# Host data including games and saves remains read-only.
# Grant writes only to manager state and the selected profile executable folder.
case "$action" in
  build|build-all|rollback|uninstall|purge|install-file|sync-deps)
    manager_state="$ROOT/data/emulator-manager"
    [[ ! -L "$manager_state" ]] || { echo "ERRO: gerenciador symlink." >&2; exit 1; }
    mkdir -p "$manager_state"
    docker_args+=(
      --mount "type=bind,src=$manager_state,dst=/workspace/data/emulator-manager"
    )
    if [[ "$action" == "build-all" ]]; then
      writable_profiles=(kytyps5 shadps4 ppsspp melonds bsnes)
    elif [[ "$action" == "sync-deps" ]]; then
      writable_profiles=()
    else
      writable_profiles=("$id")
    fi
    for profile_id in "${writable_profiles[@]}"; do
      container_path="$ROOT/data/environments/$profile_id/emulators"
      [[ ! -L "$ROOT/data/environments" && ! -L "$ROOT/data/environments/$profile_id" && ! -L "$container_path" ]] || {
        echo "ERRO: diretório do perfil não pode ser symlink." >&2; exit 1;
      }
      mkdir -p "$container_path"
      docker_args+=(
        --mount "type=bind,src=$container_path,dst=/workspace/data/environments/$profile_id/emulators"
      )
    done
    ;;
esac

# Source sync is the only explicit exception to read-only checkout.
# It must write pinned submodule Git metadata and files on the host via scoped mounts.
if [[ "$action" == "sync-deps" ]]; then
  [[ -d "$ROOT/.git" && ! -L "$ROOT/.git" ]] || {
    echo "ERRO: sync-deps exige checkout Git normal (não worktree)." >&2; exit 1;
  }
  [[ -d "$ROOT/third_party" && ! -L "$ROOT/third_party" ]] || {
    echo "ERRO: third_party/ ausente ou symlink." >&2; exit 1;
  }
  docker_args+=(
    --mount "type=bind,src=$ROOT/.git,dst=/workspace/.git"
    --mount "type=bind,src=$ROOT/third_party,dst=/workspace/third_party"
  )
fi
docker_args+=("$tag")

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
  validate)
    docker "${docker_args[@]}" bash scripts/validate-project.sh
    ;;
  build-all)
    docker "${docker_args[@]}" python3 scripts/emulator-manager.py \
      build-all --jobs "$jobs" --yes-run-upstream-code
    ;;
  plan-deps)
    docker "${docker_args[@]}" python3 scripts/emulator-manager.py plan-deps "$id"
    ;;
  sync-deps)
    docker "${docker_args[@]}" python3 scripts/emulator-manager.py \
      sync-deps "$id" --jobs "$jobs" --yes-download-submodules
    ;;
  history|rollback|uninstall)
    docker "${docker_args[@]}" python3 scripts/emulator-manager.py "$action" "$id"
    ;;
  purge)
    docker "${docker_args[@]}" python3 scripts/emulator-manager.py       purge "$id" --yes-delete-managed-backups
    ;;
  install-file)
    [[ ! -L "$ROOT/data/imports" && -f "$ROOT/data/imports/$filename" && ! -L "$ROOT/data/imports/$filename" ]] || {
      echo "ERRO: copie o arquivo revisado para data/imports/ antes de importar." >&2; exit 1;
    }
    docker "${docker_args[@]}" python3 scripts/emulator-manager.py \
      install-file "$id" "/workspace/data/imports/$filename" \
      --sha256 "$sha" --binary-name "$binary_name"
    ;;
  logs)
    docker "${docker_args[@]}" python3 scripts/phase1-logs.py "$id"
    ;;
esac
