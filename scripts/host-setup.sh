#!/bin/sh
# Create 20 isolated console data roots and the optional host GUI/audio override.
# The dashboard remains data-blind; only runtime agents receive their own mounts.
set -eu
umask 077
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

ENV_IDS="kytyps5 shadps4 rpcs3 duckstation pcsx2 ppsspp vita3k xbox-one xenia-canary xbox-series xemu eden cemu dolphin azahar melonds mgba mupen64plus bsnes mesen"
# Fail closed if host paths could alias console data through symlinks.
for path in data data/environments; do
  if [ -L "$path" ]; then echo "ERRO: caminho de armazenamento não pode ser symlink: $path" >&2; exit 1; fi
done
for env_id in $ENV_IDS; do
  root="data/environments/$env_id"
  for path in "$root" "$root/games" "$root/bios" "$root/saves" "$root/home" "$root/emulators"; do
    if [ -L "$path" ]; then echo "ERRO: caminho de mount não pode ser symlink: $path" >&2; exit 1; fi
  done
done
for path in \
  data/environments/duckstation/home/.local \
  data/environments/duckstation/home/.local/share \
  data/environments/duckstation/home/.local/share/duckstation \
  data/environments/duckstation/home/.local/share/duckstation/bios \
  data/environments/ppsspp/bios/flash0 \
  data/environments/ppsspp/bios/flash1; do
  if [ -L "$path" ]; then echo "ERRO: caminho de BIOS montado não pode ser symlink: $path" >&2; exit 1; fi
done
for env_id in $ENV_IDS; do
  mkdir -p "data/environments/$env_id/games" \
           "data/environments/$env_id/bios" \
           "data/environments/$env_id/saves" \
           "data/environments/$env_id/home/.config" \
           "data/environments/$env_id/home/.cache" \
           "data/environments/$env_id/home/.local/state/emustack/logs" \
           "data/environments/$env_id/emulators"
done
mkdir -p data/environments/duckstation/home/.local/share/duckstation/bios
chmod 700 data/environments/duckstation/home/.local/share/duckstation/bios

PUID=$(id -u)
PGID=$(id -g)
DISPLAY_VALUE=${DISPLAY:-}
XAUTH_SRC=${XAUTHORITY:-"$HOME/.Xauthority"}
GUI_ENABLED=0
X11_SOCKET_DIR=${X11_SOCKET_DIR:-/tmp/.X11-unix}
PULSE_SOCKET="${XDG_RUNTIME_DIR:-/run/user/$PUID}/pulse/native"

# Preserve tunables and the secret generated on the first setup.
read_old() { sed -n "s/^$1=//p" .env 2>/dev/null | head -n 1 || true; }
OLD_BUILD_KYTYPS5=$(read_old BUILD_KYTYPS5)
OLD_KYTYPS5_REF=$(read_old KYTYPS5_REF)
OLD_KYTYPS5_EXPECTED_SHORT=$(read_old KYTYPS5_EXPECTED_SHORT)
OLD_APT_SNAPSHOT_TIMESTAMP=$(read_old APT_SNAPSHOT_TIMESTAMP)
OLD_DEBIAN_BASE_IMAGE=$(read_old DEBIAN_BASE_IMAGE)
OLD_INSTALL_UPSTREAM=$(read_old INSTALL_UPSTREAM)
OLD_CPU_LIMIT=$(read_old EMUSTACK_CPU_LIMIT)
OLD_MEMORY_LIMIT=$(read_old EMUSTACK_MEMORY_LIMIT)
OLD_PIDS_LIMIT=$(read_old EMUSTACK_PIDS_LIMIT)
OLD_CLI_CPU_LIMIT=$(read_old EMUSTACK_CLI_CPU_LIMIT)
OLD_CLI_MEMORY_LIMIT=$(read_old EMUSTACK_CLI_MEMORY_LIMIT)
OLD_CLI_PIDS_LIMIT=$(read_old EMUSTACK_CLI_PIDS_LIMIT)
OLD_ENV_CPU_LIMIT=$(read_old EMUSTACK_ENV_CPU_LIMIT)
OLD_ENV_MEMORY_LIMIT=$(read_old EMUSTACK_ENV_MEMORY_LIMIT)
OLD_ENV_PIDS_LIMIT=$(read_old EMUSTACK_ENV_PIDS_LIMIT)
OLD_MAX_ACTIVE_ENVIRONMENTS=$(read_old EMUSTACK_MAX_ACTIVE_ENVIRONMENTS)
OLD_MAX_ACTIVE_PER_ENV=$(read_old EMUSTACK_MAX_ACTIVE_PER_ENV)
OLD_INPUT_DEVICE=$(read_old EMUSTACK_INPUT_DEVICE)
OLD_INPUT_ENV=$(read_old EMUSTACK_INPUT_ENV)
INPUT_DEVICE=${EMUSTACK_INPUT_DEVICE:-$OLD_INPUT_DEVICE}
INPUT_ENV=${EMUSTACK_INPUT_ENV:-$OLD_INPUT_ENV}
# Keep a distinct 256-bit token per agent. A compromised environment can only
# authenticate to its own controller endpoint; the Docker networks are isolated too.

if [ -n "$INPUT_DEVICE" ]; then
  if ! command -v readlink >/dev/null 2>&1; then
    echo "ERRO: readlink é necessário para validar EMUSTACK_INPUT_DEVICE." >&2
    exit 1
  fi
  INPUT_DEVICE=$(readlink -f -- "$INPUT_DEVICE" 2>/dev/null || true)
  if ! printf '%s\n' "$INPUT_DEVICE" | grep -Eq '^/dev/input/(event|js)[0-9]+$' || [ ! -c "$INPUT_DEVICE" ]; then
    echo "ERRO: EMUSTACK_INPUT_DEVICE precisa ser um dispositivo /dev/input/eventN ou jsN existente. Teclado/mouse não devem ser mapeados por padrão." >&2
    exit 1
  fi
  case " $ENV_IDS " in
    *" $INPUT_ENV "*) ;;
    *) echo "ERRO: defina EMUSTACK_INPUT_ENV para um ID de ambiente válido antes de mapear um controle: $ENV_IDS" >&2; exit 1;;
  esac
fi

rm -f compose.override.yaml
if [ -n "$DISPLAY_VALUE" ] && [ -r "$XAUTH_SRC" ] && [ -d "$X11_SOCKET_DIR" ]; then
  install -m 600 "$XAUTH_SRC" data/host.Xauthority
  GUI_ENABLED=1
else
  echo "INFO: sessão gráfica X11/XWayland não detectada ou sem Xauthority legível. Os agentes serão headless; boot gráfico ficará desabilitado."
fi

ENV_TMP=".env.tmp.$$"
trap 'rm -f "$ENV_TMP"' EXIT HUP INT TERM
{
  printf 'PUID=%s\n' "$PUID"
  printf 'PGID=%s\n' "$PGID"
  for env_id in $ENV_IDS; do
    token_suffix=$(printf '%s' "$env_id" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
    token_key="EMUSTACK_AGENT_TOKEN_$token_suffix"
    current_token=$(printenv "$token_key" 2>/dev/null || true)
    previous_token=$(read_old "$token_key")
    token_value=${current_token:-$previous_token}
    if [ -z "$token_value" ]; then
      token_value=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
    fi
    if ! printf '%s' "$token_value" | grep -Eq '^[A-Fa-f0-9]{64,}$'; then
      echo "ERRO: $token_key deve ser hexadecimal com pelo menos 64 caracteres." >&2
      exit 1
    fi
    if grep -Fq "=$token_value" "$ENV_TMP"; then
      echo "ERRO: token duplicado detectado em $token_key; cada agente precisa de um segredo único." >&2
      exit 1
    fi
    printf '%s=%s\n' "$token_key" "$token_value"
  done
  printf 'EMUSTACK_MAX_ACTIVE_ENVIRONMENTS=%s\n' "${EMUSTACK_MAX_ACTIVE_ENVIRONMENTS:-${OLD_MAX_ACTIVE_ENVIRONMENTS:-2}}"
  printf 'EMUSTACK_MAX_ACTIVE_PER_ENV=%s\n' "${EMUSTACK_MAX_ACTIVE_PER_ENV:-${OLD_MAX_ACTIVE_PER_ENV:-2}}"
  if [ "$GUI_ENABLED" -eq 1 ]; then
    case "$DISPLAY_VALUE" in *'
'*) echo "ERRO: DISPLAY contém quebra de linha." >&2; exit 1;; esac
    printf 'DISPLAY=%s\n' "$DISPLAY_VALUE"
    printf 'XAUTHORITY_FILE=./data/host.Xauthority\n'
  fi
  if [ -S "$PULSE_SOCKET" ]; then printf 'PULSE_SOCKET=%s\n' "$PULSE_SOCKET"; fi
  if [ -n "$OLD_BUILD_KYTYPS5" ]; then printf 'BUILD_KYTYPS5=%s\n' "$OLD_BUILD_KYTYPS5"; fi
  if [ -n "$OLD_KYTYPS5_REF" ]; then printf 'KYTYPS5_REF=%s\n' "$OLD_KYTYPS5_REF"; fi
  if [ -n "$OLD_KYTYPS5_EXPECTED_SHORT" ]; then printf 'KYTYPS5_EXPECTED_SHORT=%s\n' "$OLD_KYTYPS5_EXPECTED_SHORT"; fi
  if [ -n "$OLD_APT_SNAPSHOT_TIMESTAMP" ]; then printf 'APT_SNAPSHOT_TIMESTAMP=%s\n' "$OLD_APT_SNAPSHOT_TIMESTAMP"; fi
  if [ -n "$OLD_DEBIAN_BASE_IMAGE" ]; then printf 'DEBIAN_BASE_IMAGE=%s\n' "$OLD_DEBIAN_BASE_IMAGE"; fi
  if [ -n "$OLD_INSTALL_UPSTREAM" ]; then printf 'INSTALL_UPSTREAM=%s\n' "$OLD_INSTALL_UPSTREAM"; fi
  if [ -n "${EMUSTACK_CPU_LIMIT:-$OLD_CPU_LIMIT}" ]; then printf 'EMUSTACK_CPU_LIMIT=%s\n' "${EMUSTACK_CPU_LIMIT:-$OLD_CPU_LIMIT}"; fi
  if [ -n "${EMUSTACK_MEMORY_LIMIT:-$OLD_MEMORY_LIMIT}" ]; then printf 'EMUSTACK_MEMORY_LIMIT=%s\n' "${EMUSTACK_MEMORY_LIMIT:-$OLD_MEMORY_LIMIT}"; fi
  if [ -n "${EMUSTACK_PIDS_LIMIT:-$OLD_PIDS_LIMIT}" ]; then printf 'EMUSTACK_PIDS_LIMIT=%s\n' "${EMUSTACK_PIDS_LIMIT:-$OLD_PIDS_LIMIT}"; fi
  if [ -n "${EMUSTACK_CLI_CPU_LIMIT:-$OLD_CLI_CPU_LIMIT}" ]; then printf 'EMUSTACK_CLI_CPU_LIMIT=%s\n' "${EMUSTACK_CLI_CPU_LIMIT:-$OLD_CLI_CPU_LIMIT}"; fi
  if [ -n "${EMUSTACK_CLI_MEMORY_LIMIT:-$OLD_CLI_MEMORY_LIMIT}" ]; then printf 'EMUSTACK_CLI_MEMORY_LIMIT=%s\n' "${EMUSTACK_CLI_MEMORY_LIMIT:-$OLD_CLI_MEMORY_LIMIT}"; fi
  if [ -n "${EMUSTACK_CLI_PIDS_LIMIT:-$OLD_CLI_PIDS_LIMIT}" ]; then printf 'EMUSTACK_CLI_PIDS_LIMIT=%s\n' "${EMUSTACK_CLI_PIDS_LIMIT:-$OLD_CLI_PIDS_LIMIT}"; fi
  if [ -n "${EMUSTACK_ENV_CPU_LIMIT:-$OLD_ENV_CPU_LIMIT}" ]; then printf 'EMUSTACK_ENV_CPU_LIMIT=%s\n' "${EMUSTACK_ENV_CPU_LIMIT:-$OLD_ENV_CPU_LIMIT}"; fi
  if [ -n "${EMUSTACK_ENV_MEMORY_LIMIT:-$OLD_ENV_MEMORY_LIMIT}" ]; then printf 'EMUSTACK_ENV_MEMORY_LIMIT=%s\n' "${EMUSTACK_ENV_MEMORY_LIMIT:-$OLD_ENV_MEMORY_LIMIT}"; fi
  if [ -n "${EMUSTACK_ENV_PIDS_LIMIT:-$OLD_ENV_PIDS_LIMIT}" ]; then printf 'EMUSTACK_ENV_PIDS_LIMIT=%s\n' "${EMUSTACK_ENV_PIDS_LIMIT:-$OLD_ENV_PIDS_LIMIT}"; fi
  if [ -n "$INPUT_DEVICE" ]; then printf 'EMUSTACK_INPUT_DEVICE=%s\n' "$INPUT_DEVICE"; printf 'EMUSTACK_INPUT_ENV=%s\n' "$INPUT_ENV"; fi
} > "$ENV_TMP"
chmod 600 "$ENV_TMP"
mv -f -- "$ENV_TMP" .env
trap - EXIT HUP INT TERM
chmod 600 .env

if [ "$GUI_ENABLED" -eq 1 ] || [ -n "$INPUT_DEVICE" ]; then
  # JSON is valid YAML 1.2. Only per-environment agents receive GUI access.
  python3 - "$ROOT" "$DISPLAY_VALUE" "$PULSE_SOCKET" "$GUI_ENABLED" "$INPUT_DEVICE" "$INPUT_ENV" "$ENV_IDS" "$X11_SOCKET_DIR" <<'PYGEN'
import json, sys
from pathlib import Path
root, display, pulse_socket, gui_enabled, input_device, input_env, env_ids, x11_socket_dir = sys.argv[1:9]
services = {}
for env_id in env_ids.split():
    service = {}
    if gui_enabled == "1":
        service["environment"] = {
            "DISPLAY": display,
            "XAUTHORITY": "/tmp/.Xauthority",
            "QT_X11_NO_MITSHM": "1",
            "SDL_VIDEODRIVER": "x11",
            "APPIMAGE_EXTRACT_AND_RUN": "1",
        }
        service["volumes"] = [
            {"type": "bind", "source": x11_socket_dir, "target": "/tmp/.X11-unix", "read_only": False},
            {"type": "bind", "source": str(Path(root, "data/host.Xauthority")), "target": "/tmp/.Xauthority", "read_only": True},
        ]
        if Path("/dev/dri").is_dir():
            service["devices"] = ["/dev/dri:/dev/dri"]
        if pulse_socket and Path(pulse_socket).is_socket():
            service["environment"]["PULSE_SERVER"] = "unix:/tmp/pulse/native"
            service["volumes"].append({"type": "bind", "source": pulse_socket, "target": "/tmp/pulse/native", "read_only": True})
    if input_device and env_id == input_env:
        service.setdefault("devices", []).append(f"{input_device}:{input_device}:r")
    if service:
        services[f"env-{env_id}"] = service
Path(root, "compose.override.yaml").write_text(json.dumps({"services": services}, indent=2) + "\n", encoding="utf-8")
PYGEN
  if [ "$GUI_ENABLED" -eq 1 ]; then
    if [ -S "$PULSE_SOCKET" ]; then echo "Áudio: socket PulseAudio/PipeWire montado nos ambientes (read-only)."; else echo "AVISO: socket PulseAudio/PipeWire não encontrado; áudio pode não funcionar." >&2; fi
    echo "Override X11/XWayland gerado para os agentes isolados; o dashboard não recebe DISPLAY/Xauthority."
  fi
  if [ -n "$INPUT_DEVICE" ]; then echo "Controle mapeado somente ao ambiente env-$INPUT_ENV, com permissão de leitura."; fi
fi

# Protect the root and individual persistent directories; containers use the same UID/GID.
chmod 700 data
for env_id in $ENV_IDS; do
  chmod 700 "data/environments/$env_id"
  chmod u+rwx "data/environments/$env_id/games" "data/environments/$env_id/bios" \
    "data/environments/$env_id/saves" "data/environments/$env_id/home" \
    "data/environments/$env_id/home/.config" "data/environments/$env_id/home/.cache" \
    "data/environments/$env_id/home/.local" "data/environments/$env_id/home/.local/state" \
    "data/environments/$env_id/home/.local/state/emustack" \
    "data/environments/$env_id/home/.local/state/emustack/logs" \
    "data/environments/$env_id/emulators"
done
[ ! -f data/host.Xauthority ] || chmod 600 data/host.Xauthority

cat <<MSG
EmuStack host setup concluído.
UID/GID: $PUID:$PGID
Ambientes isolados: 20
Sessão gráfica: $([ "$GUI_ENABLED" -eq 1 ] && echo habilitada || echo não configurada)
Rede: cada ambiente tem bridge própria; o dashboard orquestra todos, os agentes não se comunicam diretamente.
Tokens únicos por agente: gerados/retidos em .env (não compartilhe nem versione).
Dados persistentes: data/environments/<id>/{games,bios,saves,home,emulators}

Próximos passos:
  ./scripts/build-and-audit.sh
  docker compose ps
  # Interface: http://127.0.0.1:8765

Para NVIDIA, configure antes o NVIDIA Container Toolkit e execute:
  USE_NVIDIA=1 ./scripts/build-and-audit.sh

Sem sessão gráfica, dashboard e diagnóstico continuam disponíveis; os agentes gráficos permanecem headless até rodar novamente este script em X11/XWayland.
MSG
