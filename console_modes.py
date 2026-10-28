#!/usr/bin/env python3
"""Authentic console-system boot profiles for EmuStack.

The manager only invokes explicitly allowlisted emulator commands. Proprietary
firmware/BIOS/dashboard files are never bundled; users must supply files they
are entitled to use. A supported profile does not imply complete emulation of
all hardware features.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
SYSTEMS_PATH = Path(os.environ.get("EMUSTACK_SYSTEMS_PATH", str(ROOT / "console-systems.json")))
HOME = Path(os.environ.get("HOME", "/home/emu")).expanduser().resolve()
BIOS_DIR = Path(os.environ.get("EMUSTACK_BIOS_DIR", "/bios")).resolve()
SAVES_DIR = Path(os.environ.get("EMUSTACK_SAVES_DIR", "/saves")).resolve()
CEMU_MLC = Path(os.environ.get("EMUSTACK_CEMU_MLC_PATH", str(HOME / ".local/share/Cemu/mlc01"))).expanduser().resolve()
XEMU_CONFIG = Path(os.environ.get("EMUSTACK_XEMU_CONFIG", str(HOME / ".config/xemu/xemu.toml"))).expanduser()
XEMU_ATTESTATION = Path(os.environ.get("EMUSTACK_XEMU_ATTESTATION", str(BIOS_DIR / "xemu-dashboard-attestation.json"))).expanduser()
# PPSSPP's exploratory VSH path reads firmware from assets/flash0 relative to its working directory.
# Only the PPSSPP agent mounts its private BIOS root at this location.
PPSSPP_ASSET_DIR = Path(os.environ.get("EMUSTACK_PPSSPP_ASSET_DIR", "/opt/emustack/assets")).expanduser()


def load_systems(path: Path | None = None) -> dict[str, Any]:
    file_path = path or SYSTEMS_PATH
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Não foi possível ler console-systems.json: {exc}") from exc
    if data.get("schema_version") != 1 or not isinstance(data.get("systems"), list):
        raise RuntimeError("Formato de console-systems.json não suportado")
    seen: set[str] = set()
    for profile in data["systems"]:
        identifier = profile.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise RuntimeError(f"ID de sistema ausente ou duplicado: {identifier!r}")
        seen.add(identifier)
        if profile.get("boot_strategy") not in {
            "rpcs3-vsh", "pcsx2-bios", "duckstation-bios", "ppsspp-vsh", "xemu-dashboard", "cemu-wiiu-menu",
            "dolphin-wii-menu", "manual", "no-dashboard", "unsupported",
        }:
            raise RuntimeError(f"Estratégia de boot desconhecida para {identifier}")
    return data


def _catalog_lookup(catalog_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item.get("id", ""): item for item in catalog_payload.get("emulators", []) if isinstance(item, dict)}


def _rpcs3_vsh_paths() -> list[Path]:
    return [
        HOME / ".config/rpcs3/dev_flash/vsh/module/vsh.self",
        HOME / ".local/share/rpcs3/dev_flash/vsh/module/vsh.self",
        HOME / ".var/app/net.rpcs3.RPCS3/config/rpcs3/dev_flash/vsh/module/vsh.self",
    ]


def _pcsx2_bios_paths() -> list[Path]:
    return [BIOS_DIR / "pcsx2", HOME / ".config/PCSX2/bios", HOME / ".local/share/PCSX2/bios"]


def _duckstation_bios_paths() -> list[Path]:
    # The Compose service mounts the environment-owned BIOS folder read-only at the
    # application default so the UI and command-line boot see exactly the same dump.
    return [BIOS_DIR, HOME / ".local/share/duckstation/bios", HOME / ".config/duckstation/bios"]


def _container_mount_path(path: Path) -> str | None:
    """Map a validated host/container path back to the path visible inside the agent."""
    try:
        return "/home/emu/" + path.relative_to(HOME).as_posix()
    except ValueError:
        pass
    for root, mount in ((BIOS_DIR, "/bios"), (SAVES_DIR, "/saves")):
        try:
            return mount + "/" + path.relative_to(root).as_posix()
        except ValueError:
            continue
    return None


def _dolphin_nand_roots() -> list[Path]:
    return [
        HOME / ".local/share/dolphin-emu/Wii",
        HOME / ".config/dolphin-emu/Wii",
        HOME / "Documents/Dolphin Emulator/Wii",
    ]


def _cemu_menu_candidates(mlc_root: Path | None = None) -> list[Path]:
    root = (mlc_root or CEMU_MLC).resolve()
    base = root / "sys/title/00050010"
    return [base / region / "code/men.rpx" for region in ("10040000", "10040100", "10040200")]


def _safe_existing_file(raw_path: str, *, relative_to: Path | None = None) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip() or "\x00" in raw_path:
        return None
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (relative_to or HOME) / candidate
    try:
        # Do not accept symlinks or paths outside the two private, intentional mounts.
        current = candidate
        while current != current.parent:
            if current.is_symlink():
                return None
            current = current.parent
        resolved = candidate.resolve(strict=True)
        if not (resolved.is_relative_to(HOME) or resolved.is_relative_to(BIOS_DIR) or resolved.is_relative_to(SAVES_DIR)):
            return None
        return resolved if resolved.is_file() else None
    except (OSError, RuntimeError, ValueError):
        return None


def _xemu_configuration() -> tuple[dict[str, Any] | None, list[dict[str, Any]], Path | None]:
    checks: list[dict[str, Any]] = []
    config_path = XEMU_CONFIG
    try:
        if config_path.is_symlink() or not config_path.resolve(strict=True).is_relative_to(HOME):
            raise OSError("configuração fora do HOME privado ou symlink")
        config_path = config_path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        checks.append({"label": "xemu.toml", "ok": False, "detail": f"Configuração ausente, symlink ou fora do HOME privado: {XEMU_CONFIG}"})
        return None, checks, None
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        checks.append({"label": "xemu.toml válido", "ok": False, "detail": f"Configuração TOML inválida: {exc}"})
        return None, checks, None
    files = config.get("files", {})
    if not isinstance(files, dict):
        files = {}
    required = (("bootrom_path", "MCPX boot ROM"), ("flashrom_path", "Flash ROM / BIOS"), ("hdd_path", "HDD emulado"))
    resolved: dict[str, Path] = {}
    for key, label in required:
        found = _safe_existing_file(str(files.get(key, "")), relative_to=config_path.parent)
        ok = found is not None
        checks.append({"label": label, "ok": ok, "detail": str(found) if found else f"O campo files.{key} não aponta para um arquivo regular dentro de /bios, /saves ou do HOME deste ambiente."})
        if found:
            resolved[key] = found
    hdd = resolved.get("hdd_path")
    hdd_hash = ""
    attestation_ok = False
    if hdd:
        try:
            digest = hashlib.sha256()
            with hdd.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            hdd_hash = digest.hexdigest()
        except OSError:
            hdd_hash = ""
        attestation_detail = "Não há confirmação vinculada ao hash deste HDD. A configuração, sozinha, não demonstra que o dashboard Microsoft original esteja instalado."
        try:
            attestation_path = XEMU_ATTESTATION
            if attestation_path.is_symlink() or not attestation_path.resolve(strict=True).is_relative_to(BIOS_DIR):
                raise OSError("attestation fora de /bios ou symlink")
            payload = json.loads(attestation_path.read_text(encoding="utf-8"))
            expected_container_path = _container_mount_path(hdd)
            attestation_ok = (
                payload.get("schema_version") == 1
                and payload.get("environment_id") == "xemu"
                and payload.get("dashboard_type") == "microsoft-retail"
                and payload.get("user_confirmed") is True
                and payload.get("hdd_sha256") == hdd_hash
                and payload.get("hdd_container_path") == expected_container_path
                and bool(hdd_hash)
                and bool(expected_container_path)
            )
            if attestation_ok:
                attestation_detail = "Usuário confirmou o dashboard Microsoft de varejo; caminho e hash do HDD correspondem à declaração. O conteúdo não é validado automaticamente pelo EmuStack."
            else:
                attestation_detail = "A confirmação não corresponde ao ambiente, caminho ou hash do HDD atual. Gere novamente após revisar o HDD."
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
        checks.append({"label": "Autenticidade do dashboard (declaração do usuário)", "ok": True if attestation_ok else None, "detail": attestation_detail})
    return {"files": resolved, "hdd_sha256": hdd_hash, "attestation_ok": attestation_ok}, checks, hdd


def detect_prerequisites(profile: dict[str, Any]) -> tuple[bool, list[dict[str, Any]], str | None]:
    """Return prereq state, detail checks, and a discovered boot target if any."""
    strategy = profile.get("boot_strategy")
    checks: list[dict[str, Any]] = []
    boot_target: str | None = None

    if strategy == "rpcs3-vsh":
        found = next((path for path in _rpcs3_vsh_paths() if path.is_file() and not path.is_symlink()), None)
        checks.append({"label": "PS3 VSH/XMB firmware module", "ok": bool(found), "detail": str(found) if found else "Instale o firmware do PS3 dentro do RPCS3."})
        boot_target = str(found) if found else None
        return bool(found), checks, boot_target

    if strategy == "pcsx2-bios":
        bios_candidates: list[Path] = []
        for directory in _pcsx2_bios_paths():
            if directory.is_dir() and not directory.is_symlink():
                try:
                    bios_candidates.extend(path for path in directory.glob("*.bin") if path.is_file() and not path.is_symlink())
                except OSError:
                    pass
        found = bool(bios_candidates)
        checks.append({"label": "PS2 BIOS dump encontrado", "ok": found, "detail": f"{len(bios_candidates)} arquivo(s) .bin encontrado(s); confirme a seleção em Settings → BIOS." if found else "Nenhum BIOS .bin detectado em /bios/pcsx2/ (host: data/environments/pcsx2/bios/pcsx2/) ou na pasta de BIOS do PCSX2."})
        return found, checks, str(bios_candidates[0]) if found else None

    if strategy == "duckstation-bios":
        bios_candidates: list[Path] = []
        for directory in _duckstation_bios_paths():
            if directory.is_dir() and not directory.is_symlink():
                try:
                    bios_candidates.extend(path for path in directory.iterdir()
                                           if path.is_file() and not path.is_symlink()
                                           and path.suffix.lower() in {".bin", ".rom"})
                except OSError:
                    pass
        found = bool(bios_candidates)
        checks.append({"label": "PS1 BIOS dump encontrado", "ok": found,
                       "detail": f"{len(bios_candidates)} arquivo(s) BIOS detectado(s); confirme a seleção no DuckStation." if found else
                       "Nenhum BIOS .bin/.rom detectado em data/environments/duckstation/bios/. O BIOS original não é incluído no EmuStack."})
        return found, checks, str(bios_candidates[0]) if found else None

    if strategy == "ppsspp-vsh":
        flash0 = PPSSPP_ASSET_DIR / "flash0"
        required = [flash0 / "vsh/module/vshmain.prx", flash0 / "kd/pspbtcnf.bin"]
        labels = ["PSP VSH module", "PSP firmware kernel configuration"]
        checks.append({"label": "Diretório flash0 do firmware PSP", "ok": flash0.is_dir() and not flash0.is_symlink(),
                       "detail": str(flash0) if flash0.is_dir() and not flash0.is_symlink() else
                       "Coloque o dump autorizado do firmware PSP em data/environments/ppsspp/bios/flash0/."})
        for path, label in zip(required, labels):
            # Every component between the mount root and required firmware files must be a real path,
            # not a symlink that could redirect outside this console environment.
            safe = True
            current = path
            while current != PPSSPP_ASSET_DIR and current != current.parent:
                if current.is_symlink():
                    safe = False
                    break
                current = current.parent
            ok = safe and path.is_file() and not path.is_symlink()
            checks.append({"label": label, "ok": ok,
                           "detail": str(path) if ok else f"Arquivo ausente ou caminho com symlink: {path}"})
        ready = all(bool(item.get("ok")) for item in checks)
        checks.append({"label": "Nível de suporte", "ok": None,
                       "detail": "O boot VSH/XMB do PPSSPP é um caminho experimental do upstream; firmware detectado não garante o funcionamento de todas as funções."})
        return ready, checks, str(flash0) if ready else None

    if strategy == "xemu-dashboard":
        configuration, xemu_checks, hdd = _xemu_configuration()
        checks.extend(xemu_checks)
        if configuration and all(configuration["files"].get(key) for key in ("bootrom_path", "flashrom_path", "hdd_path")):
            checks.append({"label": "Arquivos do sistema do Xbox", "ok": True, "detail": "MCPX, BIOS e HDD existem e estão dentro dos mounts privados deste ambiente."})
            attested = bool(configuration.get("attestation_ok"))
            return attested, checks, str(XEMU_CONFIG)
        return False, checks, None

    if strategy == "dolphin-wii-menu":
        installed = None
        for root in _dolphin_nand_roots():
            title_dir = root / "title/00000001/00000002"
            if title_dir.is_dir() and not title_dir.is_symlink():
                installed = title_dir
                break
        checks.append({"label": "Wii System Menu instalado no NAND", "ok": bool(installed), "detail": str(installed) if installed else "Instale o Wii System Menu no Dolphin e mantenha o NAND no home persistente."})
        return bool(installed), checks, str(installed) if installed else None

    if strategy == "cemu-wiiu-menu":
        found = next((path for path in _cemu_menu_candidates() if path.is_file() and not path.is_symlink()), None)
        checks.append({"label": "Wii U Menu (men.rpx) encontrado", "ok": bool(found), "detail": str(found) if found else f"Menu não detectado em {CEMU_MLC}/sys/title/00050010/<região>/code/men.rpx."})
        return bool(found), checks, str(found) if found else None

    if strategy == "manual":
        checks.append({"label": "Boot do menu pelo frontend do emulador", "ok": None, "detail": "O projeto não expõe um comando CLI estável para iniciar esse menu diretamente; abra o emulador e siga os passos específicos."})
        return False, checks, None

    if strategy == "no-dashboard":
        checks.append({"label": "Dashboard de sistema", "ok": False, "detail": "Esta geração não possui um dashboard de aplicações equivalente ao XMB/Home Menu; a sequência de boot aparece no contexto de BIOS/jogo."})
        return False, checks, None

    checks.append({"label": "Boot de sistema completo", "ok": False, "detail": profile.get("details", "Não suportado pelo emulador atual.")})
    return False, checks, None


def resolve_systems(
    catalog_payload: dict[str, Any],
    status_fn: Callable[[dict[str, Any]], tuple[str, str | None]],
    systems_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    payload = systems_payload or load_systems()
    emulators = _catalog_lookup(catalog_payload)
    resolved: list[dict[str, Any]] = []
    for raw in payload["systems"]:
        profile = dict(raw)
        associated = [emulators[eid] for eid in profile.get("emulator_ids", []) if eid in emulators]
        found_binary: str | None = None
        runtime_statuses: list[str] = []
        for emulator in associated:
            status, binary = status_fn(emulator)
            runtime_statuses.append(status)
            if binary and not found_binary:
                found_binary = binary
        profile["runtime_statuses"] = runtime_statuses
        profile["binary_found"] = bool(found_binary)
        profile["binary_name"] = Path(found_binary).name if found_binary else None
        prerequisites_met, checks, target = detect_prerequisites(profile)
        profile["checks"] = checks
        profile["boot_target"] = target
        strategy = profile["boot_strategy"]
        has_launcher = bool(found_binary)
        if strategy == "unsupported":
            profile["state"] = "unsupported"
            profile["state_label"] = "Boot de sistema não suportado"
            profile["can_boot_original"] = False
            profile["can_open_emulator"] = has_launcher
        elif strategy == "no-dashboard":
            profile["state"] = "no-dashboard"
            profile["state_label"] = "Sem dashboard nesta geração"
            profile["can_boot_original"] = False
            profile["can_open_emulator"] = has_launcher
        elif not has_launcher:
            profile["state"] = "launcher-missing"
            profile["state_label"] = "Emulador não instalado"
            profile["can_boot_original"] = False
            profile["can_open_emulator"] = False
        elif strategy == "manual":
            profile["state"] = "manual"
            profile["state_label"] = "Inicialização manual no emulador"
            profile["can_boot_original"] = False
            profile["can_open_emulator"] = True
        elif strategy == "ppsspp-vsh":
            if prerequisites_met:
                profile["state"] = "experimental-ready"
                profile["state_label"] = "PSP XMB experimental · firmware detectado; boot não verificado"
                profile["can_boot_original"] = True
                profile["can_open_emulator"] = True
                profile["runtime_boot_tested"] = False
                profile["runtime_boot_note"] = "PPSSPP documenta --vsh como caminho exploratório. O flash0 foi detectado; a interface e suas funções ainda precisam de teste visual neste host."
            else:
                profile["state"] = "needs-setup"
                profile["state_label"] = "Firmware PSP flash0 ausente/incompleto"
                profile["can_boot_original"] = False
                profile["can_open_emulator"] = True
        elif strategy == "xemu-dashboard":
            configuration, _xemu_checks, _hdd = _xemu_configuration()
            files_ready = bool(configuration and all(configuration.get("files", {}).get(key) for key in ("bootrom_path", "flashrom_path", "hdd_path")))
            attested = bool(configuration and configuration.get("attestation_ok"))
            if attested:
                profile["state"] = "user-attested"
                profile["state_label"] = "Xbox original configurado · dashboard confirmado pelo usuário"
                profile["can_boot_original"] = True
                profile["dashboard_authenticity"] = "user-attested-hash-bound"
            elif files_ready:
                profile["state"] = "needs-verification"
                profile["state_label"] = "Arquivos detectados · dashboard original não confirmado"
                profile["can_boot_original"] = False
                profile["dashboard_authenticity"] = "unverified"
            else:
                profile["state"] = "needs-setup"
                profile["state_label"] = "Configure MCPX, BIOS e HDD do Xbox"
                profile["can_boot_original"] = False
                profile["dashboard_authenticity"] = "unverified"
            profile["can_open_emulator"] = has_launcher
        elif prerequisites_met:
            profile["state"] = "ready"
            profile["state_label"] = "Pré-requisitos detectados"
            profile["can_boot_original"] = True
            profile["can_open_emulator"] = True
            profile["runtime_boot_tested"] = False
            profile["runtime_boot_note"] = "Pré-requisitos detectados; o EmuStack ainda não observou uma inicialização real bem-sucedida neste host."
        else:
            profile["state"] = "needs-setup"
            profile["state_label"] = "Precisa configurar firmware/sistema"
            profile["can_boot_original"] = False
            profile["can_open_emulator"] = True
        resolved.append(profile)
    return resolved


def build_boot_command(system_id: str, binary: str, systems_payload: dict[str, Any] | None = None) -> list[str]:
    payload = systems_payload or load_systems()
    profile = next((item for item in payload["systems"] if item.get("id") == system_id), None)
    if not profile:
        raise ValueError(f"Sistema desconhecido: {system_id}")
    strategy = profile["boot_strategy"]
    if strategy == "rpcs3-vsh":
        found = next((path for path in _rpcs3_vsh_paths() if path.is_file() and not path.is_symlink()), None)
        if not found:
            raise ValueError("O módulo VSH não foi encontrado. Instale o firmware do PS3 no RPCS3 primeiro.")
        return [binary, str(found)]
    if strategy == "pcsx2-bios":
        ready, _checks, _target = detect_prerequisites(profile)
        if not ready:
            raise ValueError("Não foi encontrado um BIOS do PS2. Configure o BIOS autorizado no PCSX2 primeiro.")
        return [binary, "-bios", "-fullscreen"]
    if strategy == "duckstation-bios":
        ready, _checks, _target = detect_prerequisites(profile)
        if not ready:
            raise ValueError("Não foi encontrado um BIOS do PS1. Coloque o dump autorizado em data/environments/duckstation/bios/ e confirme a configuração do DuckStation.")
        return [binary, "-bios", "-fullscreen"]
    if strategy == "ppsspp-vsh":
        ready, _checks, _target = detect_prerequisites(profile)
        if not ready:
            raise ValueError("Boot PSP XMB indisponível: coloque seu dump autorizado em data/environments/ppsspp/bios/flash0/ com vsh/module/vshmain.prx e kd/pspbtcnf.bin. O recurso --vsh é experimental no upstream.")
        # PPSSPP's upstream CLI documents --vsh and --fullscreen. Do not use
        # --memstick because that flag is only present in newer 1.21+ builds;
        # the persistent HOME of this agent keeps the memory stick isolated.
        return [binary, "--vsh", "--fullscreen"]
    if strategy == "xemu-dashboard":
        ready, _checks, _target = detect_prerequisites(profile)
        if not ready:
            raise ValueError("Boot autenticado do dashboard Xbox bloqueado: configure MCPX/BIOS/HDD no xemu.toml e gere uma confirmação vinculada ao hash do HDD após verificar que ele contém o dashboard Microsoft original. O EmuStack não consegue identificar o dashboard dentro da imagem de forma independente.")
        return [binary, "-full-screen", "-config_path", str(XEMU_CONFIG)]
    if strategy == "dolphin-wii-menu":
        ready, _checks, _target = detect_prerequisites(profile)
        if not ready:
            raise ValueError("O Wii System Menu não foi encontrado no NAND do Dolphin.")
        # 0000000100000002 is the Wii System Menu title ID. Dolphin's CLI supports
        # --nand_title; no third-party wrapper or shell is involved.
        return [binary, "--nand_title=0000000100000002"]
    if strategy == "cemu-wiiu-menu":
        found = next((path for path in _cemu_menu_candidates() if path.is_file() and not path.is_symlink()), None)
        if not found:
            raise ValueError("men.rpx não encontrado na MLC configurada do Cemu.")
        return [binary, "--mlc", str(CEMU_MLC), "--game", str(found), "--fullscreen"]
    raise ValueError(f"Não existe boot automático verificado para {profile['name']}; consulte setup_steps e detalhes.")


def system_by_id(system_id: str, systems_payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = systems_payload or load_systems()
    return next((dict(item) for item in payload["systems"] if item.get("id") == system_id), None)
