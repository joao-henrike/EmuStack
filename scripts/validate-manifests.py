#!/usr/bin/env python3
"""Cross-validate EmuStack JSON manifests and Docker Compose wiring.

This validator checks references and deployment wiring; it does not claim that an
upstream emulator was downloaded, that a binary runs, or that a console/game boots.
PyYAML is required to validate Compose (CI installs it before running this script).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

JSON_MANIFESTS = (
    "catalog.json",
    "environments.json",
    "console-systems.json",
    "game-sources.json",
    "release-lock.json",
)
COMPOSE_FILES = ("compose.yaml", "compose.nvidia.yaml")
BOOT_STRATEGIES = {
    "rpcs3-vsh",
    "pcsx2-bios",
    "duckstation-bios",
    "ppsspp-vsh",
    "xemu-dashboard",
    "cemu-wiiu-menu",
    "dolphin-wii-menu",
    "manual",
    "no-dashboard",
    "unsupported",
}
LOCK_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
LOCK_URL_HOSTS = {"stable.eden-emu.dev", "dl.dolphin-emu.org"}


def _load_json(root: Path, filename: str, errors: list[str]) -> dict:
    path = root / filename
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{filename}: arquivo obrigatório ausente")
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{filename}: não foi possível ler JSON válido: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{filename}: o documento raiz precisa ser um objeto JSON")
        return {}
    if value.get("schema_version") != 1:
        errors.append(f"{filename}: schema_version deve ser 1")
    return value


def _records(data: dict, key: str, filename: str, errors: list[str]) -> list[dict]:
    value = data.get(key)
    if not isinstance(value, list):
        errors.append(f"{filename}: campo '{key}' precisa ser uma lista")
        return []
    result: list[dict] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{filename}: {key}[{index}] precisa ser um objeto")
            continue
        result.append(item)
    return result


def _id_map(items: list[dict], label: str, errors: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for index, item in enumerate(items):
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            errors.append(f"{label}[{index}]: campo 'id' obrigatório e não vazio")
            continue
        if identifier in result:
            errors.append(f"{label}: ID duplicado '{identifier}'")
            continue
        result[identifier] = item
    return result


def _is_safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "\x00" not in value


def _parse_volume(volume: object) -> tuple[str, str, str] | None:
    if isinstance(volume, str):
        parts = volume.split(":")
        if len(parts) < 2:
            return None
        return parts[0], parts[1], parts[2] if len(parts) >= 3 else ""
    if isinstance(volume, dict):
        source = volume.get("source")
        target = volume.get("target")
        mode = "ro" if volume.get("read_only") else "rw"
        if isinstance(source, str) and isinstance(target, str):
            return source, target, mode
    return None


def _check_compose(root: Path, environments: dict[str, dict], errors: list[str]) -> None:
    try:
        import yaml
    except ImportError:
        errors.append("Compose: PyYAML ausente; instale com 'python3 -m pip install pyyaml'")
        return

    loaded: dict[str, dict] = {}
    for filename in COMPOSE_FILES:
        path = root / filename
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            errors.append(f"{filename}: arquivo Compose obrigatório ausente")
            continue
        except Exception as exc:
            errors.append(f"{filename}: YAML inválido: {exc}")
            continue
        if not isinstance(document, dict) or not isinstance(document.get("services"), dict):
            errors.append(f"{filename}: esperado objeto Compose com 'services'")
            continue
        loaded[filename] = document

    if "compose.yaml" not in loaded:
        return
    base = loaded["compose.yaml"]
    services = base["services"]
    networks = base.get("networks", {})
    if not isinstance(networks, dict):
        errors.append("compose.yaml: 'networks' precisa ser um objeto")
        networks = {}

    dashboard = services.get("dashboard")
    if not isinstance(dashboard, dict):
        errors.append("compose.yaml: serviço 'dashboard' ausente ou inválido")
        dashboard = {}
    dashboard_env = dashboard.get("environment", {})
    if not isinstance(dashboard_env, dict):
        dashboard_env = {}
        errors.append("compose.yaml: dashboard.environment precisa ser um mapa")
    dashboard_networks = dashboard.get("networks", {})
    if not isinstance(dashboard_networks, dict):
        dashboard_networks = {}

    expected_services = {item.get("service_name") for item in environments.values()}
    declared_agent_services = {name for name in services if name.startswith("env-")}
    for missing in sorted(expected_services - set(services)):
        errors.append(f"compose.yaml: serviço declarado em environments.json mas ausente: '{missing}'")
    for extra in sorted(declared_agent_services - expected_services):
        errors.append(f"compose.yaml: serviço de agente sem ambiente correspondente: '{extra}'")

    expected_gateways: set[str] = set()
    env_items = list(environments.values())
    for index, environment in enumerate(env_items, start=1):
        identifier = environment.get("id", "<sem-id>")
        service_name = environment.get("service_name")
        service = services.get(service_name)
        if not isinstance(service, dict):
            continue
        service_env = service.get("environment", {})
        if not isinstance(service_env, dict):
            errors.append(f"compose.yaml:{service_name}: environment precisa ser um mapa")
            service_env = {}
        if service_env.get("EMUSTACK_ENV_ID") != identifier:
            errors.append(
                f"compose.yaml:{service_name}: EMUSTACK_ENV_ID deveria ser '{identifier}', "
                f"recebido {service_env.get('EMUSTACK_ENV_ID')!r}"
            )
        if service_env.get("EMUSTACK_SYSTEMS_PATH") != "/opt/emustack/console-systems.json":
            errors.append(f"compose.yaml:{service_name}: EMUSTACK_SYSTEMS_PATH ausente ou incorreto")
        if service_env.get("EMUSTACK_ENVIRONMENTS_PATH") != "/opt/emustack/environments.json":
            errors.append(f"compose.yaml:{service_name}: EMUSTACK_ENVIRONMENTS_PATH ausente ou incorreto")

        directory_map = environment.get("directories", {})
        volumes = service.get("volumes", [])
        parsed_volumes = [_parse_volume(item) for item in volumes] if isinstance(volumes, list) else []
        expected_mounts = (
            ("games", "/games", "ro"),
            ("bios", "/bios", "ro"),
            ("saves", "/saves", "rw"),
            ("config_home", "/home/emu", "rw"),
            ("custom_emulators", "/custom-emulators", "ro"),
        )
        for directory_key, target, mode in expected_mounts:
            relative = directory_map.get(directory_key) if isinstance(directory_map, dict) else None
            expected_source = f"./{relative}" if isinstance(relative, str) else None
            matching = [
                item for item in parsed_volumes
                if item is not None and item[0] in (expected_source, relative)
                and item[1] == target and item[2].split(",")[0] == mode
            ]
            if not matching:
                errors.append(
                    f"compose.yaml:{service_name}: mount de '{directory_key}' deveria mapear "
                    f"{relative!r} para {target}:{mode}"
                )

        network_name = f"env-{identifier}-net"
        service_networks = service.get("networks", {})
        if not isinstance(service_networks, dict) or network_name not in service_networks:
            errors.append(f"compose.yaml:{service_name}: conexão à rede '{network_name}' ausente")
            continue
        if network_name not in dashboard_networks:
            errors.append(f"compose.yaml: dashboard não está conectado à rede '{network_name}'")
        network = networks.get(network_name)
        if not isinstance(network, dict):
            errors.append(f"compose.yaml: definição da rede '{network_name}' ausente")
            continue
        if network.get("internal") is not True:
            errors.append(f"compose.yaml:{network_name}: a bridge do agente precisa ser internal: true")
        network_config = network.get("ipam", {}).get("config", [])
        expected_subnet = f"172.28.{index}.0/24"
        if not network_config or network_config[0].get("subnet") != expected_subnet:
            errors.append(f"compose.yaml:{network_name}: subnet esperada {expected_subnet}")
        elif network_config[0].get("gateway") != f"172.28.{index}.1":
            errors.append(f"compose.yaml:{network_name}: gateway esperada 172.28.{index}.1")
        expected_gateways.add(f"172.28.{index}.1")
        address = service_networks[network_name]
        if not isinstance(address, dict) or address.get("ipv4_address") != f"172.28.{index}.2":
            errors.append(f"compose.yaml:{service_name}: IP do agente deveria ser 172.28.{index}.2")
        dashboard_address = dashboard_networks.get(network_name)
        if not isinstance(dashboard_address, dict) or dashboard_address.get("ipv4_address") != f"172.28.{index}.3":
            errors.append(f"compose.yaml: IP do dashboard em {network_name} deveria ser 172.28.{index}.3")

    trusted_raw = dashboard_env.get("EMUSTACK_CONTROL_TRUSTED_CLIENT_IPS", "")
    trusted = {part.strip() for part in str(trusted_raw).split(",") if part.strip()}
    if trusted != expected_gateways:
        errors.append("compose.yaml: EMUSTACK_CONTROL_TRUSTED_CLIENT_IPS não corresponde às gateways isoladas")

    if "compose.nvidia.yaml" in loaded:
        overlay_services = loaded["compose.nvidia.yaml"]["services"]
        if not isinstance(overlay_services, dict):
            errors.append("compose.nvidia.yaml: 'services' precisa ser um mapa")
        else:
            for name in overlay_services:
                if name not in expected_services:
                    errors.append(f"compose.nvidia.yaml: serviço '{name}' não corresponde a um ambiente conhecido")


def validate_repository(root: Path, include_compose: bool = True) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    documents = {
        name: _load_json(root, name, errors)
        for name in JSON_MANIFESTS
    }

    catalog = documents["catalog.json"]
    environments_doc = documents["environments.json"]
    systems_doc = documents["console-systems.json"]
    sources_doc = documents["game-sources.json"]
    lock_doc = documents["release-lock.json"]

    emulators = _records(catalog, "emulators", "catalog.json", errors)
    environments = _records(environments_doc, "environments", "environments.json", errors)
    systems = _records(systems_doc, "systems", "console-systems.json", errors)
    sources = _records(sources_doc, "sources", "game-sources.json", errors)
    categories = _records(sources_doc, "categories", "game-sources.json", errors)

    emulator_map = _id_map(emulators, "catalog.json:emulators", errors)
    environment_map = _id_map(environments, "environments.json:environments", errors)
    system_map = _id_map(systems, "console-systems.json:systems", errors)
    source_map = _id_map(sources, "game-sources.json:sources", errors)
    category_map = _id_map(categories, "game-sources.json:categories", errors)

    catalog_ids = set(emulator_map)
    environment_ids = set(environment_map)
    system_ids = set(system_map)
    if catalog_ids != environment_ids:
        errors.append(
            "catalog/environment ID mismatch: "
            f"sem ambiente={sorted(catalog_ids - environment_ids)}, "
            f"sem emulador={sorted(environment_ids - catalog_ids)}"
        )

    for identifier, emulator in emulator_map.items():
        if not isinstance(emulator.get("name"), str) or not emulator["name"].strip():
            errors.append(f"catalog.json:{identifier}: name obrigatório")
        for field in ("commands", "binary_names"):
            value = emulator.get(field)
            if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
                errors.append(f"catalog.json:{identifier}: '{field}' deve ser uma lista de strings não vazias")
        url = emulator.get("url")
        if url and (urlparse(str(url)).scheme != "https" or not urlparse(str(url)).netloc):
            errors.append(f"catalog.json:{identifier}: URL deve ser HTTPS válida")

    required_directory_keys = {"root", "games", "bios", "saves", "config_home", "custom_emulators"}
    service_names: set[str] = set()
    for identifier, environment in environment_map.items():
        if environment.get("emulator_id") not in catalog_ids:
            errors.append(f"environments.json:{identifier}: emulator_id inexistente {environment.get('emulator_id')!r}")
        service_name = environment.get("service_name")
        if service_name != f"env-{identifier}":
            errors.append(f"environments.json:{identifier}: service_name esperado 'env-{identifier}'")
        if service_name in service_names:
            errors.append(f"environments.json:{identifier}: service_name duplicado {service_name!r}")
        if isinstance(service_name, str):
            service_names.add(service_name)
        directory_map = environment.get("directories")
        if not isinstance(directory_map, dict):
            errors.append(f"environments.json:{identifier}: directories precisa ser um mapa")
            directory_map = {}
        missing_keys = required_directory_keys - set(directory_map)
        if missing_keys:
            errors.append(f"environments.json:{identifier}: diretórios ausentes {sorted(missing_keys)}")
        root_path = f"data/environments/{identifier}"
        if directory_map.get("root") != root_path:
            errors.append(f"environments.json:{identifier}: root esperado '{root_path}'")
        for key, value in directory_map.items():
            if not _is_safe_relative_path(value):
                errors.append(f"environments.json:{identifier}: caminho não relativo/seguro em directories.{key}: {value!r}")
            elif key != "root" and not str(value).startswith(root_path + "/"):
                errors.append(f"environments.json:{identifier}: directories.{key} sai da raiz do ambiente")
        profile_ids = environment.get("system_profile_ids")
        if not isinstance(profile_ids, list):
            errors.append(f"environments.json:{identifier}: system_profile_ids precisa ser uma lista")
        else:
            for system_id in profile_ids:
                if system_id not in system_ids:
                    errors.append(f"environments.json:{identifier}: system_profile_id inexistente {system_id!r}")

    for identifier, system in system_map.items():
        strategy = system.get("boot_strategy")
        if strategy not in BOOT_STRATEGIES:
            errors.append(f"console-systems.json:{identifier}: boot_strategy inválida {strategy!r}")
        emulator_ids = system.get("emulator_ids")
        if not isinstance(emulator_ids, list):
            errors.append(f"console-systems.json:{identifier}: emulator_ids precisa ser uma lista")
            continue
        for emulator_id in emulator_ids:
            if emulator_id not in catalog_ids:
                errors.append(f"console-systems.json:{identifier}: emulator_id inexistente {emulator_id!r}")

    for identifier, source in source_map.items():
        if not isinstance(source.get("name"), str) or not source["name"].strip():
            errors.append(f"game-sources.json:{identifier}: name obrigatório")
        if source.get("category") not in category_map:
            errors.append(f"game-sources.json:{identifier}: category desconhecida {source.get('category')!r}")
        url = source.get("url")
        parsed = urlparse(str(url or ""))
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"game-sources.json:{identifier}: URL deve ser HTTPS válida")

    lock_items = lock_doc.get("items")
    if not isinstance(lock_items, dict):
        errors.append("release-lock.json: items precisa ser um objeto por ID de emulador")
        lock_items = {}
    if lock_doc.get("strict") is not True:
        errors.append("release-lock.json: strict precisa ser true para o perfil de CI deste projeto")
    lock_ids = set(lock_items)
    if lock_ids != catalog_ids:
        errors.append(
            "release-lock/catalog ID mismatch: "
            f"sem lock={sorted(catalog_ids - lock_ids)}, "
            f"lock sem emulador={sorted(lock_ids - catalog_ids)}"
        )
    for identifier, item in lock_items.items():
        if not isinstance(item, dict):
            errors.append(f"release-lock.json:{identifier}: entrada precisa ser um objeto")
            continue
        mode = item.get("mode")
        if mode == "pinned":
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", str(item.get("repo", ""))):
                errors.append(f"release-lock.json:{identifier}: repo de lock inválido")
            if not str(item.get("tag", "")).strip() or not str(item.get("asset", "")).strip():
                errors.append(f"release-lock.json:{identifier}: tag/asset precisam ser fixados")
            if not LOCK_SHA256.fullmatch(str(item.get("sha256", ""))):
                errors.append(f"release-lock.json:{identifier}: SHA-256 inválido")
        elif mode == "pinned-url":
            parsed = urlparse(str(item.get("url", "")))
            if parsed.scheme != "https" or parsed.hostname not in LOCK_URL_HOSTS:
                errors.append(f"release-lock.json:{identifier}: host da URL fixada não permitido")
            if not LOCK_SHA256.fullmatch(str(item.get("sha256", ""))):
                errors.append(f"release-lock.json:{identifier}: SHA-256 inválido")
        elif mode == "skip-upstream":
            if not isinstance(item.get("reason"), str) or not item["reason"].strip():
                errors.append(f"release-lock.json:{identifier}: skip-upstream exige justificativa")
        else:
            errors.append(f"release-lock.json:{identifier}: modo desconhecido {mode!r}")

    if include_compose:
        _check_compose(root, environment_map, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--skip-compose", action="store_true", help="validate JSON manifests only")
    args = parser.parse_args()
    errors = validate_repository(args.root, include_compose=not args.skip_compose)
    if errors:
        print(f"MANIFEST VALIDATION FAILED: {len(errors)} error(s)", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    catalog = json.loads((args.root / "catalog.json").read_text(encoding="utf-8"))
    environments = json.loads((args.root / "environments.json").read_text(encoding="utf-8"))
    systems = json.loads((args.root / "console-systems.json").read_text(encoding="utf-8"))
    sources = json.loads((args.root / "game-sources.json").read_text(encoding="utf-8"))
    lock = json.loads((args.root / "release-lock.json").read_text(encoding="utf-8"))
    pinned = sum(1 for item in lock["items"].values() if item.get("mode") in {"pinned", "pinned-url"})
    skipped = sum(1 for item in lock["items"].values() if item.get("mode") == "skip-upstream")
    print(
        "MANIFEST VALIDATION OK: "
        f"{len(catalog['emulators'])} emulators, {len(environments['environments'])} environments, "
        f"{len(systems['systems'])} system profiles, {len(sources['sources'])} sources; "
        f"{pinned} pinned lock entries and {skipped} explicit skips; Compose wiring valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
