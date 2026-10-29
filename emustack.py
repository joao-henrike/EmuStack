#!/usr/bin/env python3
"""EmuStack launcher: inventory and launch frontend for multiple emulator runtimes."""
from __future__ import annotations
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path
import console_modes
from typing import Any

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = Path(os.environ.get("EMUSTACK_CATALOG", str(ROOT / "catalog.json")))
BIN_DIR = Path(os.environ.get("EMUSTACK_BIN_DIR", "/opt/emustack/installed"))
USER_BIN_DIR = Path(os.environ.get("EMUSTACK_USER_BIN_DIR", "/custom-emulators"))
INSTALL_REPORT = Path(os.environ.get("EMUSTACK_INSTALL_REPORT", str(ROOT / "install-report.json")))
GAMES_DIR = Path(os.environ.get("EMUSTACK_GAMES_DIR", "/games"))


def catalog() -> dict[str, Any]:
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERRO: não foi possível ler o catálogo {CATALOG_PATH}: {exc}")
    if data.get("schema_version") != 1 or not isinstance(data.get("emulators"), list):
        raise SystemExit("ERRO: formato de catálogo não suportado.")
    return data


def find_binary(item: dict[str, Any]) -> str | None:
    # User-supplied verified binaries take precedence, but remain mounted read-only.
    roots = [USER_BIN_DIR, BIN_DIR]
    names = item.get("binary_names", [])
    for root in roots:
        for name in names:
            path = root / name
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
        # Release archives can contain a nested project directory. Search only the
        # explicit catalog names and never execute an arbitrary first file found.
        if root.is_dir():
            for name in names:
                try:
                    matches = sorted(root.rglob(name))
                except OSError:
                    matches = []
                for path in matches:
                    if path.is_file() and os.access(path, os.X_OK):
                        return str(path)
    for name in item.get("commands", []):
        path = shutil.which(name)
        if path:
            return path
    return None


def runtime_status(item: dict[str, Any]) -> tuple[str, str | None]:
    if item.get("runtime") == "unsupported" or item.get("game_arg") == "blocked":
        return "NO SUPPORTED EMULATOR", None
    if item.get("runtime") == "windows-only":
        return "NO LINUX EMULATOR BIN", None
    if item.get("runtime") == "research-project":
        return "NO STANDALONE RUNNER", None
    if item.get("runtime") == "unverified-variant":
        return "UNVERIFIED VARIANT", None
    binary = find_binary(item)
    if binary:
        if binary.lower().endswith(".exe") and not (shutil.which("wine") or shutil.which("wine64")):
            return "NEEDS WINE", None
        return ("AVAILABLE VIA WINE" if binary.lower().endswith(".exe") else "AVAILABLE"), binary
    if item.get("runtime") == "windows-or-wine" and shutil.which("wine"):
        return "NEEDS BINARY", None
    return "NOT INSTALLED", None


def print_table() -> None:
    items = catalog()["emulators"]
    headers = ("ID", "CONSOLE", "STATUS", "RUNTIME")
    rows = []
    for item in items:
        status, binary = runtime_status(item)
        label = status if not binary else f"{status}: {Path(binary).name}"
        rows.append((item["id"], item["platform"], label, item["runtime"]))
    widths = [max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(4)]
    print("  ".join(headers[i].ljust(widths[i]) for i in range(4)))
    print("  ".join("-" * widths[i] for i in range(4)))
    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(4)))
    print(f"\n{len(items)} entries. AVAILABLE means a launcher binary was found, not that games are fully compatible.")
    print(f"Image-installed binaries: {BIN_DIR}")
    print(f"User drop-in binaries/AppImages (read-only mount): {USER_BIN_DIR}")


def doctor() -> int:
    print("EmuStack — diagnóstico do container")
    checks: list[tuple[str, bool, str]] = []
    display = os.environ.get("DISPLAY")
    checks.append(("DISPLAY", bool(display), display or "não definido; aplicativos gráficos não abrirão na sessão do host"))
    x_socket = Path("/tmp/.X11-unix")
    checks.append(("X11 socket", x_socket.exists(), str(x_socket)))
    checks.append(("Vulkan loader", bool(shutil.which("vulkaninfo")) or Path("/usr/lib/x86_64-linux-gnu/libvulkan.so.1").exists(), "libvulkan/vulkaninfo"))
    checks.append(("/games", GAMES_DIR.is_dir(), str(GAMES_DIR)))
    checks.append(("installed binary directory", BIN_DIR.is_dir(), str(BIN_DIR)))
    checks.append(("user drop-in directory", USER_BIN_DIR.is_dir(), str(USER_BIN_DIR)))
    checks.append(("Wine", bool(shutil.which("wine")), shutil.which("wine") or "não instalado; necessário apenas para certos executáveis Windows"))
    try:
        report = json.loads(INSTALL_REPORT.read_text(encoding="utf-8"))
        items = report.get("items", {})
        ok_count = sum(1 for value in items.values() if value.get("status") == "installed")
        checks.append(("upstream install report", True, f"{ok_count} entry/entries installed or downloaded; {INSTALL_REPORT}"))
    except (OSError, json.JSONDecodeError):
        checks.append(("upstream install report", False, f"not found/readable: {INSTALL_REPORT}"))
    for name, ok, detail in checks:
        print(f"[{'OK' if ok else 'AVISO'}] {name}: {detail}")
    print("\nGPU: execute `vulkaninfo --summary` para confirmar o driver dentro do container.")
    print("Controles: o container não recebe /dev/input automaticamente. Mapeie apenas o dispositivo necessário se quiser usar um controle.")
    return 0


def safe_game_path(arg: str) -> Path:
    path = Path(arg).expanduser()
    if not path.is_absolute():
        path = GAMES_DIR / path
    # The argument must resolve under /games, unless caller explicitly enables outside paths.
    allow_external = os.environ.get("EMUSTACK_ALLOW_EXTERNAL_GAMES", "0") == "1"
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        raise SystemExit(f"ERRO: jogo/arquivo não encontrado ou caminho inválido: {path}")
    if not allow_external:
        try:
            resolved.relative_to(GAMES_DIR.resolve())
        except ValueError:
            raise SystemExit(f"ERRO: por segurança, o arquivo deve estar dentro de {GAMES_DIR}. Para exceção consciente, defina EMUSTACK_ALLOW_EXTERNAL_GAMES=1.")
    if not resolved.is_file():
        raise SystemExit(f"ERRO: o caminho selecionado não é um arquivo regular: {resolved}")
    return resolved



def build_release_lock(report_payload: dict[str, Any], catalog_payload: dict[str, Any]) -> dict[str, Any]:
    """Export an opt-in lock for successfully downloaded upstream release assets.

    This intentionally excludes Debian packages and source builds because the
    installer report does not yet attest those inputs with immutable versions.
    """
    report_items = report_payload.get("items", {})
    lock_items: dict[str, dict[str, Any]] = {}
    sha_pattern = re.compile(r"^[a-fA-F0-9]{64}$")
    repo_pattern = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    allowed_url_hosts = {
        "eden": {"stable.eden-emu.dev"},
        "dolphin": {"dl.dolphin-emu.org"},
    }

    for emulator in catalog_payload.get("emulators", []):
        identifier = emulator.get("id")
        if not isinstance(identifier, str) or not identifier:
            continue
        report_item = report_items.get(identifier, {})
        sha256 = str(report_item.get("sha256", "")).lower()
        version = str(report_item.get("version", ""))
        repo = str(report_item.get("repo", ""))
        asset = str(report_item.get("asset", ""))
        if report_item.get("status") == "installed" and repo and asset and sha_pattern.fullmatch(sha256):
            if repo_pattern.fullmatch(repo) and asset not in {".", ".."} and "/" not in asset and "\\" not in asset and version not in {"", "unknown", "source build", "Debian package"}:
                lock_items[identifier] = {
                    "mode": "pinned",
                    "repo": repo,
                    "tag": version,
                    "asset": asset,
                    "sha256": sha256,
                }
                continue
        url = str(report_item.get("url", ""))
        parsed = urllib.parse.urlparse(url)
        allowed_hosts = allowed_url_hosts.get(identifier, set())
        if (report_item.get("status") == "installed" and parsed.scheme == "https"
                and (parsed.hostname or "").lower() in allowed_hosts
                and sha_pattern.fullmatch(sha256) and version not in {"", "unknown", "source build", "Debian package"}):
            lock_items[identifier] = {
                "mode": "pinned-url",
                "url": url,
                "version": version,
                "asset": asset or Path(parsed.path).name,
                "sha256": sha256,
            }
            continue
        status = str(report_item.get("status", "not-reported"))
        reason = "not a pinnable official release asset"
        if report_item.get("source") == "APT fallback" or version == "Debian package":
            reason = "APT package versions are not pinned by this lockfile"
        elif version == "source build" or identifier == "kytyps5":
            reason = "source commit/build inputs are not pinned by this lockfile"
        elif status != "installed":
            reason = f"upstream binary not installed in captured report (status={status})"
        lock_items[identifier] = {"mode": "skip-upstream", "reason": reason}

    return {
        "schema_version": 1,
        "strict": True,
        "project": "EmuStack",
        "generated_from_version": str(report_payload.get("version", "unknown")),
        "scope": "Pins downloadable official release assets observed during the build. Entries marked `pinned` or `pinned-url` contain SHA-256 hashes; `skip-upstream` entries are deliberately not installed from a pinned upstream asset. The current lock does not pin or claim a KytyPS5 source build. The Debian base-image digest is pinned; Debian APT versions are time-pinned only when APT_SNAPSHOT_TIMESTAMP is set. This does not guarantee bit-for-bit reproducibility across architectures/build environments.",
        "items": lock_items,
    }


def export_release_lock() -> int:
    try:
        report_payload = json.loads(INSTALL_REPORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Não foi possível exportar o lockfile: relatório indisponível/ inválido em {INSTALL_REPORT}: {exc}")
    payload = build_release_lock(report_payload, catalog())
    # Keep stdout as valid JSON so this can be redirected straight to release-lock.json.
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return 0

def launch(identifier: str, game: str | None, extra_args: list[str]) -> int:
    matches = [e for e in catalog()["emulators"] if e["id"] == identifier.lower()]
    if not matches:
        valid = ", ".join(e["id"] for e in catalog()["emulators"])
        raise SystemExit(f"Emulador desconhecido: {identifier}\nIDs: {valid}")
    item = matches[0]
    if item.get("game_arg") == "blocked":
        raise SystemExit(f"{item['name']} não pode ser iniciado por este container Linux: {item['notes']}\nProjeto: {item['url']}")
    status, binary = runtime_status(item)
    if not binary:
        raise SystemExit(f"{item['name']}: launcher não encontrado ({status}).\nInstale um pacote compatível ou coloque um executável/AppImage oficial em {BIN_DIR}.\nReferência: {item['url']}")
    if not os.environ.get("DISPLAY"):
        raise SystemExit("ERRO: DISPLAY não está configurado. Execute scripts/host-setup.sh numa sessão X11/XWayland e recrie o container gráfico antes de iniciar emuladores.")
    is_windows_exe = binary.lower().endswith(".exe")
    if is_windows_exe:
        wine = shutil.which("wine") or shutil.which("wine64")
        if not wine:
            raise SystemExit("Este executável requer Wine, mas `wine` não está disponível no container.")
        args = [wine, binary]
    else:
        args = [binary]
    if game:
        game_path = safe_game_path(game)
        mode = item.get("game_arg", "append")
        extension = game_path.suffix.lower()
        if mode == "ui-only":
            raise SystemExit(f"{item['name']} recebe o conteúdo pela própria interface e não aceita este caminho como argumento. Inicie o emulador sem arquivo e escolha o conteúdo pela interface.")
        elif mode == "blocked":
            raise SystemExit(f"Lançamento bloqueado: {item['name']} — {item.get('notes', 'runtime não suportado')}.")
        elif item["id"] == "rpcs3" and extension in {".rap", ".edat"}:
            raise SystemExit("Arquivo RAP/EDAT é dado de licença/suporte, não um jogo inicializável. Abra RPCS3 e use a interface de instalação/gestão de licenças.")
        elif item["id"] == "rpcs3" and extension == ".pkg":
            # RPCS3 package files need the package-install command, not generic boot-game syntax.
            args.extend(["--installpkg", str(game_path)])
        else:
            args.append(str(game_path))
    args.extend(extra_args)
    print("Executando:", " ".join(shlex.quote(a) for a in args), flush=True)
    try:
        proc = subprocess.run(args, check=False)
        return int(proc.returncode)
    except OSError as exc:
        raise SystemExit(f"Falha ao executar {binary}: {exc}")


def boot_system(system_id: str) -> int:
    """Boot an authentic console firmware/menu through a verified emulator path."""
    try:
        systems_payload = console_modes.load_systems()
    except RuntimeError as exc:
        raise SystemExit(str(exc))
    profile = console_modes.system_by_id(system_id, systems_payload)
    if not profile:
        raise SystemExit(f"Sistema desconhecido: {system_id}")
    if profile.get("boot_strategy") in {"unsupported", "no-dashboard", "manual"}:
        manual = "; ".join(profile.get("setup_steps", [])) or "não disponíveis"
        raise SystemExit(
            f"Não existe boot automático de sistema para {profile['name']}: "
            f"{profile.get('details', 'verifique a documentação do emulador')}\n"
            f"Passos manuais: {manual}"
        )
    if not os.environ.get("DISPLAY"):
        raise SystemExit("ERRO: DISPLAY não está configurado para iniciar a interface gráfica do sistema emulado.")
    data = catalog()
    entries = {item.get("id"): item for item in data.get("emulators", [])}
    emulator = None
    binary = None
    for emulator_id in profile.get("emulator_ids", []):
        candidate = entries.get(emulator_id)
        if candidate:
            _status, candidate_binary = runtime_status(candidate)
            if candidate_binary:
                emulator, binary = candidate, candidate_binary
                break
    if not emulator or not binary:
        raise SystemExit(f"Emulador não instalado para {profile['name']}; confira `emustack list`.")
    resolved = console_modes.resolve_systems(data, runtime_status, systems_payload)
    state = next((item for item in resolved if item.get("id") == system_id), None)
    if not state or not state.get("can_boot_original"):
        checks = state.get("checks", []) if state else []
        detail = "\n".join(f"- {item.get('label')}: {item.get('detail')}" for item in checks)
        raise SystemExit(f"Pré-requisitos do sistema original não foram atendidos.\n{detail}")
    try:
        command = console_modes.build_boot_command(system_id, binary, systems_payload)
    except ValueError as exc:
        raise SystemExit(str(exc))
    if profile.get("id") == "xbox-original-dashboard":
        print("Iniciando o hardware emulado do Xbox original em tela cheia.", flush=True)
        print("A confirmação é uma declaração do usuário vinculada ao SHA-256 do HDD; o EmuStack não identifica automaticamente o conteúdo do dashboard.", flush=True)
    else:
        print(f"Iniciando interface do sistema: {profile['name']} — {profile['interface_name']}", flush=True)
    print("Comando:", " ".join(shlex.quote(part) for part in command), flush=True)
    try:
        result = subprocess.run(command, check=False)
        return int(result.returncode)
    except OSError as exc:
        raise SystemExit(f"Falha ao iniciar interface de sistema: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="emustack", description="Catálogo e lançador Docker para emuladores de consoles.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="lista todos os projetos e detecta launchers instalados")
    sub.add_parser("doctor", help="verifica sessão gráfica, Vulkan, diretórios e Wine")
    launch_parser = sub.add_parser("launch", help="inicia um emulador disponível")
    launch_parser.add_argument("emulator", help="ID exibido por `list`")
    launch_parser.add_argument("game", nargs="?", help="caminho relativo a /games ou caminho permitido pelo modo externo")
    launch_parser.add_argument("extra_args", nargs=argparse.REMAINDER, help="argumentos adicionais passados ao emulador")
    sub.add_parser("catalog", help="imprime a localização do catálogo e conta os projetos")
    sub.add_parser("install-report", help="mostra o relatório de downloads e builds upstream")
    sub.add_parser("export-lock", help="exporta JSON lockado para assets upstream já instalados")
    boot_parser = sub.add_parser("boot-system", help="inicia firmware/menu nativo quando o emulador oferece suporte")
    boot_parser.add_argument("system", help="ID listado em console-systems.json")
    web_parser = sub.add_parser("web", help="inicia o dashboard web local")
    web_parser.add_argument("--host", default="127.0.0.1", help="endereço de bind (padrão: loopback)")
    web_parser.add_argument("--port", type=int, default=8765, help="porta HTTP local")
    args = parser.parse_args()
    if args.command == "list":
        print_table()
        return 0
    if args.command == "doctor":
        return doctor()
    if args.command == "catalog":
        data = catalog()
        print(f"{CATALOG_PATH} — {len(data['emulators'])} projetos")
        return 0
    if args.command == "install-report":
        try:
            print(INSTALL_REPORT.read_text(encoding="utf-8"))
            return 0
        except OSError as exc:
            raise SystemExit(f"Relatório de instalação indisponível: {INSTALL_REPORT}: {exc}")
    if args.command == "export-lock":
        return export_release_lock()
    if args.command == "boot-system":
        return boot_system(args.system)
    if args.command == "launch":
        return launch(args.emulator, args.game, args.extra_args)
    if args.command == "web":
        from webapp import serve
        return serve(args.host, args.port, catalog, runtime_status, safe_game_path)
    return 2

if __name__ == "__main__":
    sys.exit(main())
