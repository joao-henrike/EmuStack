#!/usr/bin/env bash
set -Eeuo pipefail
die() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }
info() { printf '\n==> %s\n' "$*"; }

[[ $# -eq 1 ]] || die "Uso: bash IMPORT-LOCAL.sh /caminho/EmuStack-Docker-0.7.1.zip"
command -v git >/dev/null 2>&1 || die "Git não está instalado."
command -v sha256sum >/dev/null 2>&1 || die "sha256sum não está disponível."
command -v unzip >/dev/null 2>&1 || die "Instale o pacote unzip."

archive="$(realpath -- "$1")"
[[ -f "$archive" ]] || die "Arquivo ZIP não encontrado: $archive"
expected_sha="3753467d99c7ef1e73cce9d1fc0262b60a2a95bc83804994ea35b1b66ce97771"
actual_sha="$(sha256sum -- "$archive" | awk '{print $1}')"
[[ "$actual_sha" == "$expected_sha" ]] || die "SHA-256 divergente. Esperado: $expected_sha; recebido: $actual_sha"

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || die "Execute este script dentro de um clone Git do EmuStack."
repo_root="$(realpath -- "$repo_root")"
branch="$(git -C "$repo_root" branch --show-current)"
[[ "$branch" == "main" ]] || die "A branch atual é '$branch', não 'main'. Mude para main antes do import."

remote="$(git -C "$repo_root" remote get-url origin 2>/dev/null || true)"
case "$remote" in
  https://github.com/joao-henrike/EmuStack.git|https://github.com/joao-henrike/EmuStack|git@github.com:joao-henrike/EmuStack.git|ssh://git@github.com/joao-henrike/EmuStack.git) ;;
  *) die "Remote origin inesperado: '$remote'. O destino deve ser o repositório privado joao-henrike/EmuStack." ;;
esac
status="$(git -C "$repo_root" status --porcelain)"
[[ -z "$status" ]] || die "A árvore de trabalho não está limpa. Não sobrescreverei alterações locais; confira: git status"

tracked="$(git -C "$repo_root" ls-files | LC_ALL=C sort)"
expected_tracked="$(printf '%s\n' .github/workflows/import-source.yml IMPORT-LOCAL.sh README.md docs/GAME_SOURCES.md | LC_ALL=C sort)"
[[ "$tracked" == "$expected_tracked" ]] || die "O repositório contém arquivos rastreados além dos arquivos de bootstrap esperados. Revise antes do import."

tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
info "Validando a estrutura do ZIP"
unzip -tqq "$archive" || die "O ZIP está corrompido."
unzip -q "$archive" -d "$tmp"
src="$tmp/EmuStack-0.7.1"
[[ -d "$src" && -f "$src/README.md" && -f "$src/Dockerfile" && -f "$src/compose.yaml" && -f "$src/emustack.py" && -f "$src/game-sources.json" && -d "$src/scripts" && -d "$src/tests" && -d "$src/web" ]] || die "A árvore do pacote 0.7.1 não tem a estrutura esperada."

find "$src" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$src" -type f -name '*.pyc' -delete
if find "$src" -type f \( -name '.env' -o -name 'id_rsa' -o -name 'id_ed25519' -o -name '*.pem' -o -name '*.key' \) -print -quit | grep -q .; then
  die "Foi encontrado um arquivo de segredo/chave no pacote; importação cancelada."
fi
for rel in data/games data/bios data/home data/saves data/config data/environments emulators; do
  if [[ -d "$src/$rel" ]]; then
    extra="$(find "$src/$rel" -type f ! -name '.gitkeep' -print -quit)"
    [[ -z "$extra" ]] || die "Dados locais detectados em '$rel'; não serão enviados ao GitHub."
  fi
done

info "Copiando a árvore completa de EmuStack 0.7.1"
cp -a "$src/." "$repo_root/"
rm -f "$repo_root/IMPORT-LOCAL.sh" "$repo_root/.github/workflows/import-source.yml"
rmdir --ignore-fail-on-non-empty "$repo_root/.github/workflows" "$repo_root/.github" 2>/dev/null || true
find "$repo_root/scripts" -maxdepth 1 -type f -name '*.sh' -exec chmod +x {} +

git -C "$repo_root" add -A
git -C "$repo_root" diff --cached --check || die "A verificação de whitespace falhou."
info "Arquivos que serão publicados"
git -C "$repo_root" diff --cached --stat
printf '\nDestino: %s (repositório privado)\n' "$remote"
printf 'SHA-256 verificado: %s\n' "$actual_sha"
read -r -p "Criar o commit e enviar o projeto completo EmuStack 0.7.1 para origin/main? [y/N] " answer
case "$answer" in y|Y|yes|YES|s|S|sim|SIM) ;; *) die "Cancelado pelo usuário; nada foi enviado." ;; esac

git -C "$repo_root" commit -m "Import complete EmuStack 0.7.1 project source"
git -C "$repo_root" push origin HEAD:main
info "Importação concluída. Confira Dockerfile, compose.yaml, scripts/, tests/, web/ e docs/ na branch main."
