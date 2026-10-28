#!/usr/bin/env bash
# Build the image, report detected launchers and start the local dashboard.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERRO: Docker CLI não encontrado. Instale/ative Docker Engine + Compose v2 no host." >&2
  exit 127
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERRO: o plugin Docker Compose v2 não está disponível." >&2
  exit 127
fi
if ! docker info >/dev/null 2>&1; then
  echo "ERRO: não foi possível falar com o daemon Docker. Inicie-o e confirme as permissões do usuário." >&2
  exit 1
fi

compose=(docker compose -f compose.yaml)
# Explicit -f flags disable Compose's implicit auto-loading of compose.override.yaml,
# so include the host-generated GUI/audio configuration deliberately when present.
if [[ -f compose.override.yaml ]]; then
  compose+=(-f compose.override.yaml)
fi
if [[ "${USE_NVIDIA:-0}" == "1" ]]; then
  if [[ ! -f compose.nvidia.yaml ]]; then
    echo "ERRO: compose.nvidia.yaml não encontrado." >&2
    exit 1
  fi
  compose+=(-f compose.nvidia.yaml)
fi

printf '\n== 0/6: testes e validações estáticas ==\n'
./scripts/validate-project.sh
printf '\n== 1/6: validando configuração Compose ==\n'
"${compose[@]}" config --quiet
printf '\n== 2/6: construindo imagem e instalando ativos oficiais ==\n'
"${compose[@]}" build --progress=plain
if [[ "${FREEZE_RELEASE_LOCK:-0}" == "1" ]]; then
  lock_tmp="$(mktemp "${ROOT}/release-lock.json.new.XXXXXX")"
  lock_old="$(mktemp "${ROOT}/release-lock.json.old.XXXXXX")"
  trap 'rm -f "${lock_tmp:-}" "${lock_old:-}"' EXIT HUP INT TERM
  cp release-lock.json "$lock_old"
  printf '\n== Pinning hashes of successfully downloaded official releases ==\n'
  "${compose[@]}" run --rm --no-deps emustack export-lock > "$lock_tmp"
  python3 scripts/check-release-lock.py "$lock_tmp" --require-strict --require-pins
  mv "$lock_tmp" release-lock.json
  if ! "${compose[@]}" build --progress=plain; then
    cp "$lock_old" release-lock.json
    echo 'ERRO: rebuild com lock estrito falhou; lock anterior restaurado.' >&2
    exit 1
  fi
  rm -f "$lock_old"
  trap - EXIT HUP INT TERM
  python3 scripts/check-release-lock.py release-lock.json --require-strict
fi
printf '\n== 3/6: relatório de instalações ==\n'
"${compose[@]}" run --rm emustack install-report
printf '\n== 4/6: inventário e diagnóstico ==\n'
"${compose[@]}" run --rm emustack list
"${compose[@]}" run --rm emustack doctor
printf '\n== 5/6: iniciando dashboard local ==\n'
"${compose[@]}" up -d dashboard
if [[ "${RUN_RUNTIME_ACCEPTANCE:-0}" == "1" ]]; then
  printf '\n== Runtime acceptance (host Docker, GUI/GPU/game tests still separate) ==\n'
  USE_NVIDIA="${USE_NVIDIA:-0}" ./scripts/runtime-acceptance.sh
fi
printf '\nInterface EmuStack: http://127.0.0.1:8765\n'
