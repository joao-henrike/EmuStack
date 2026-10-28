#!/usr/bin/env python3
"""Local-only EmuStack web dashboard. Uses only Python's standard library."""
from __future__ import annotations

import ipaddress
import json
import mimetypes
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
import console_modes
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DOCS_DIR = Path(os.environ.get("EMUSTACK_WEB_DOCS_DIR", str(ROOT / "docs"))).resolve()
SOURCES_PATH = Path(os.environ.get("EMUSTACK_SOURCES_PATH", str(ROOT / "game-sources.json"))).resolve()
GAMES_DIR = Path(os.environ.get("EMUSTACK_GAMES_DIR", "/games")).resolve()
INSTALL_REPORT = Path(os.environ.get("EMUSTACK_INSTALL_REPORT", "/opt/emustack/install-report.json"))
CATALOG_PATH = Path(os.environ.get("EMUSTACK_CATALOG", str(ROOT / "catalog.json")))
CLI_PATH = ROOT / "emustack.py"
SYSTEMS_PATH = Path(os.environ.get("EMUSTACK_SYSTEMS_PATH", str(ROOT / "console-systems.json")))
ENVIRONMENTS_PATH = Path(os.environ.get("EMUSTACK_ENVIRONMENTS_PATH", str(ROOT / "environments.json")))
ISOLATED_MODE = os.environ.get("EMUSTACK_ISOLATED_MODE", "0") == "1"
AGENT_PORT = int(os.environ.get("EMUSTACK_AGENT_PORT", "8877"))
MAX_ACTIVE_ENVIRONMENTS = max(1, int(os.environ.get("EMUSTACK_MAX_ACTIVE_ENVIRONMENTS", "2")))

GAME_EXTENSIONS = {
    ".iso", ".cso", ".chd", ".cue", ".bin", ".img", ".mdf", ".pbp", ".pkg", ".elf", ".self",
    ".gcm", ".rvz", ".wbfs", ".wud", ".wux", ".wua", ".nsp", ".xci", ".nro", ".3ds", ".cci",
    ".cia", ".edat", ".nds", ".gba", ".gbc", ".gb", ".nes", ".sfc", ".smc", ".n64", ".z64", ".v64",
    ".pce", ".32x", ".md", ".gen", ".sms", ".gg", ".a26", ".a52", ".lnx", ".tap", ".d64",
    ".adf", ".wad", ".dol", ".gcz", ".ciso", ".wii", ".xex", ".xcp",
}
MAX_GAMES = 3000
MAX_REQUEST = 16 * 1024
MAX_ACTIVE_PROCESSES = 8
MAX_TRACKED_PROCESSES = 100
MAX_RETAINED_LOG_FILES = 100
MAX_PROCESS_LOG_BYTES = 128 * 1024
# In Compose mode, only Docker bridge gateway addresses are allowed to originate
# state-changing dashboard requests. Environment containers use fixed .2 addresses
# and cannot spoof a trusted TCP source address. Host-native mode remains loopback-only.
CONTROL_TRUSTED_CLIENT_IPS = frozenset(
    ipaddress.ip_address(value.strip())
    for value in os.environ.get("EMUSTACK_CONTROL_TRUSTED_CLIENT_IPS", "").split(",")
    if value.strip()
)


def _is_trusted_dashboard_client(client_ip: str) -> bool:
    # Accept local host clients and explicitly configured Docker gateway sources only.
    try:
        address = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    return address.is_loopback or address in CONTROL_TRUSTED_CLIENT_IPS
LOG_DIR = Path(os.environ.get("EMUSTACK_LOG_DIR", "/home/emu/.local/state/emustack/logs")).resolve()
PROCESS_LOCK = threading.RLock()
PROCESS_REGISTRY: dict[int, dict[str, Any]] = {}
LAUNCH_RESERVATIONS = 0
ACTIVE_ENVIRONMENT_RESERVATIONS: dict[str, int] = {}


def _capture_process_output(process: subprocess.Popen, log_path: Path) -> None:
    """Drain child output continuously while retaining only the final bounded log tail."""
    stream = getattr(process, "stdout", None)
    if stream is None:
        return
    buffer = bytearray()
    try:
        with log_path.open("wb") as destination:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) > MAX_PROCESS_LOG_BYTES:
                    del buffer[: len(buffer) - MAX_PROCESS_LOG_BYTES]
                destination.seek(0)
                destination.write(buffer)
                destination.truncate()
                destination.flush()
    except (OSError, ValueError):
        # A logging failure must not block a game process or crash the dashboard.
        return
    finally:
        try:
            stream.close()
        except (OSError, AttributeError):
            pass


def _process_state(record: dict[str, Any]) -> str:
    process = record["process"]
    if process.poll() is None:
        return "running"
    if record.get("stop_requested"):
        return "stopped"
    return "exited" if process.returncode == 0 else "failed"


def _public_process(record: dict[str, Any]) -> dict[str, Any]:
    process = record["process"]
    return {
        "pid": int(process.pid),
        "emulator": record["emulator"],
        "emulator_name": record["emulator_name"],
        "game": record.get("game"),
        "started_at": record["started_at"],
        "status": _process_state(record),
        "exit_code": process.returncode,
        "log_available": Path(record["log_path"]).is_file(),
    }


def _process_snapshots() -> list[dict[str, Any]]:
    with PROCESS_LOCK:
        records = list(PROCESS_REGISTRY.values())
    return sorted((_public_process(record) for record in records), key=lambda item: item["started_at"], reverse=True)


def _read_log_tail(path: Path) -> tuple[str, bool]:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            truncated = size > MAX_PROCESS_LOG_BYTES
            handle.seek(max(0, size - MAX_PROCESS_LOG_BYTES), os.SEEK_SET)
            data = handle.read(MAX_PROCESS_LOG_BYTES)
        return data.decode("utf-8", errors="replace"), truncated
    except OSError:
        return "Log ainda não disponível.", False


def _prune_log_files() -> None:
    """Keep persistent session logs bounded across repeated launches/restarts."""
    try:
        candidates = [item for item in LOG_DIR.glob("*.log") if not item.is_dir()]
        candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError:
        return
    for path in candidates[MAX_RETAINED_LOG_FILES:]:
        try:
            path.unlink()
        except OSError:
            pass


def _prune_process_registry() -> None:
    with PROCESS_LOCK:
        if len(PROCESS_REGISTRY) <= MAX_TRACKED_PROCESSES:
            return
        completed = [
            (pid, record) for pid, record in PROCESS_REGISTRY.items()
            if record["process"].poll() is not None
        ]
        completed.sort(key=lambda pair: pair[1]["started_at"])
        for pid, _record in completed[: max(0, len(PROCESS_REGISTRY) - MAX_TRACKED_PROCESSES)]:
            removed = PROCESS_REGISTRY.pop(pid, None)
            if removed:
                try:
                    Path(removed["log_path"]).unlink(missing_ok=True)
                except OSError:
                    pass


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def environment_manifest() -> dict[str, Any]:
    payload = load_json(ENVIRONMENTS_PATH, {})
    if payload.get("schema_version") != 1 or not isinstance(payload.get("environments"), list):
        raise RuntimeError(f"Manifesto de ambientes inválido: {ENVIRONMENTS_PATH}")
    identifiers = [item.get("id") for item in payload["environments"]]
    if len(identifiers) != len(set(identifiers)) or any(not isinstance(item, str) for item in identifiers):
        raise RuntimeError("O manifesto tem IDs de ambientes duplicados ou inválidos.")
    return payload


def _known_environment_ids() -> set[str]:
    try:
        return {item["id"] for item in environment_manifest()["environments"]}
    except RuntimeError:
        return set()


def _agent_request(environment_id: str, route: str, payload: dict[str, Any] | None = None, timeout: float = 1.2) -> tuple[int, dict[str, Any]] | None:
    """Call an allowlisted environment agent over its private Compose network."""
    if environment_id not in _known_environment_ids() or not re.fullmatch(r"[a-z0-9-]{1,80}", environment_id):
        return None
    url = f"http://env-{environment_id}:{AGENT_PORT}{route}"
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    agent_token_key = "EMUSTACK_AGENT_TOKEN_" + environment_id.upper().replace("-", "_")
    headers = {"Accept": "application/json", "X-EmuStack-Agent-Token": os.environ.get(agent_token_key, "")}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method="GET" if body is None else "POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(64 * 1024)
            data = json.loads(raw.decode("utf-8")) if raw else {}
            return int(response.status), data if isinstance(data, dict) else {}
    except HTTPError as exc:
        try:
            raw = exc.read(64 * 1024)
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = {}
        return int(exc.code), data if isinstance(data, dict) else {}
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None


def _agent_health_map() -> dict[str, dict[str, Any] | None]:
    if not ISOLATED_MODE:
        return {}
    try:
        identifiers = [item["id"] for item in environment_manifest()["environments"]]
    except RuntimeError:
        return {}
    result: dict[str, dict[str, Any] | None] = {}
    with ThreadPoolExecutor(max_workers=min(20, max(1, len(identifiers)))) as pool:
        futures = {pool.submit(_agent_request, eid, "/health", None, 0.8): eid for eid in identifiers}
        for future in as_completed(futures):
            eid = futures[future]
            response = future.result()
            if response and response[0] == 200 and response[1].get("healthy"):
                result[eid] = response[1]
            else:
                result[eid] = None
    return result


def environment_records(catalog_payload: dict[str, Any] | None = None, status_fn: Callable[[dict[str, Any]], tuple[str, str | None]] | None = None) -> list[dict[str, Any]]:
    """Return the 20 environment manifests with live-agent health attached."""
    catalog_payload = catalog_payload or load_json(CATALOG_PATH, {"emulators": []})
    try:
        manifest = environment_manifest()
    except RuntimeError:
        return []
    catalog_by_id = {item.get("id"): item for item in catalog_payload.get("emulators", [])}
    health_map = _agent_health_map() if ISOLATED_MODE else {}
    records = []
    for raw in manifest["environments"]:
        env = dict(raw)
        eid = env["id"]
        emulator = catalog_by_id.get(eid, {})
        health = health_map.get(eid) if ISOLATED_MODE else None
        if ISOLATED_MODE:
            online = bool(health)
            binary_found = bool(health and health.get("binary_found"))
            runtime_status = str(health.get("runtime_status", "AGENT_OFFLINE")) if health else "AGENT_OFFLINE"
            binary_name = health.get("binary_name") if health else None
        else:
            status, binary = status_fn(emulator) if status_fn and emulator else ("UNKNOWN", None)
            online = False
            binary_found = bool(binary)
            runtime_status = status
            binary_name = Path(binary).name if binary else None
        env.update({
            "online": online,
            "agent_status": "online" if online else ("not-managed-in-this-mode" if not ISOLATED_MODE else "offline"),
            "runtime_status": runtime_status,
            "binary_found": binary_found,
            "binary_name": binary_name,
            "launch_available": bool(binary_found and emulator and emulator.get("game_arg") != "blocked" and (online if ISOLATED_MODE else True)),
            "active_sessions": int(health.get("active_sessions", 0)) if health else 0,
            "emulator_url": emulator.get("url", env.get("url", "")),
            "directories": env.get("directories", {}),
        })
        records.append(env)
    return records


def _fetch_agent_route(environment_id: str, route: str, timeout: float = 1.2) -> tuple[int, dict[str, Any]] | None:
    return _agent_request(environment_id, route, None, timeout)


def _agent_processes() -> list[dict[str, Any]]:
    if not ISOLATED_MODE:
        return _process_snapshots()
    try:
        identifiers = [item["id"] for item in environment_manifest()["environments"]]
    except RuntimeError:
        return []
    result: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(20, max(1, len(identifiers)))) as pool:
        futures = {pool.submit(_fetch_agent_route, eid, "/processes", 0.8): eid for eid in identifiers}
        for future in as_completed(futures):
            eid = futures[future]
            response = future.result()
            if not response or response[0] != 200:
                continue
            for record in response[1].get("processes", []):
                local_id = str(record.get("session_id", ""))
                record["local_session_id"] = local_id
                record["environment_id"] = eid
                record["session_key"] = f"{eid}--{local_id}"
                result.append(record)
    return sorted(result, key=lambda item: item.get("started_at", ""), reverse=True)


def get_game_files() -> list[dict[str, Any]]:
    if ISOLATED_MODE:
        try:
            records = environment_manifest()["environments"]
        except RuntimeError:
            return []
        result: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(20, max(1, len(records)))) as pool:
            futures = {pool.submit(_fetch_agent_route, env["id"], "/games", 1.2): env for env in records}
            for future in as_completed(futures):
                env = futures[future]
                response = future.result()
                if not response or response[0] != 200:
                    continue
                for game in response[1].get("games", []):
                    game["environment_id"] = env["id"]
                    game["environment_name"] = env.get("name", env["id"])
                    result.append(game)
        result.sort(key=lambda item: (item.get("environment_name", "").casefold(), item.get("path", "").casefold()))
        return result[:MAX_GAMES]

    games: list[dict[str, Any]] = []
    if not GAMES_DIR.is_dir():
        return games
    try:
        for path in GAMES_DIR.rglob("*"):
            if len(games) >= MAX_GAMES:
                break
            try:
                if path.is_symlink() or not path.is_file() or any(p.startswith(".") for p in path.relative_to(GAMES_DIR).parts):
                    continue
                if path.suffix.lower() not in GAME_EXTENSIONS:
                    continue
                stat = path.stat()
                rel = path.relative_to(GAMES_DIR).as_posix()
                games.append({
                    "path": rel, "name": path.name, "extension": path.suffix.lower() or "folder",
                    "size_bytes": stat.st_size, "size_label": format_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                })
            except (OSError, ValueError):
                continue
    except OSError:
        return []
    games.sort(key=lambda item: item["path"].casefold())
    return games


def _resolved_console_systems(catalog_fn: Callable[[], dict[str, Any]], status_fn: Callable[[dict[str, Any]], tuple[str, str | None]]) -> list[dict[str, Any]]:
    systems_payload = console_modes.load_systems(SYSTEMS_PATH)
    if not ISOLATED_MODE:
        return console_modes.resolve_systems(catalog_fn(), status_fn, systems_payload)
    resolved: list[dict[str, Any]] = []
    for raw in systems_payload["systems"]:
        profile = dict(raw)
        emulator_ids = profile.get("emulator_ids", [])
        if not emulator_ids:
            static = console_modes.resolve_systems(catalog_fn(), status_fn, {"schema_version": systems_payload.get("schema_version", 1), "systems": [raw]})[0]
            static["environment_online"] = False
            resolved.append(static)
            continue
        candidates: list[dict[str, Any]] = []
        for eid in emulator_ids:
            response = _agent_request(eid, f"/system-status?system={quote(profile['id'])}", None, 1.0)
            if response and response[0] == 200:
                candidates.append(response[1])
        if candidates:
            selected = next((item for item in candidates if item.get("binary_found")), candidates[0])
            resolved.append(selected)
            continue
        profile.update({
            "state": "environment-offline", "state_label": "Ambiente isolado indisponível",
            "can_boot_original": False, "can_open_emulator": False,
            "binary_found": False, "environment_online": False,
            "environment_id": emulator_ids[0],
            "checks": [{"label": "Agente isolado", "ok": False, "detail": f"O ambiente env-{emulator_ids[0]} não respondeu. Inicie/recrie os serviços com Docker Compose."}],
        })
        resolved.append(profile)
    return resolved


def summarize(catalog_fn: Callable[[], dict[str, Any]], status_fn: Callable[[dict[str, Any]], tuple[str, str | None]]) -> dict[str, Any]:
    entries = catalog_fn().get("emulators", [])
    if ISOLATED_MODE:
        envs = environment_records(catalog_fn(), status_fn)
        ready = sum(1 for env in envs if env.get("launch_available"))
        needs_attention = sum(1 for env in envs if env.get("online") and env.get("runtime_status") not in ("AVAILABLE", "AVAILABLE VIA WINE"))
        online_count = sum(1 for env in envs if env.get("online"))
        processes = _agent_processes()
        games = get_game_files()
        return {
            "project": "EmuStack", "version": "0.7.1", "emulator_count": len(entries),
            "environment_count": len(envs), "environments_online": online_count,
            "launchers_ready": ready, "needs_attention": needs_attention,
            "game_count": len(games), "game_bytes": sum(g.get("size_bytes", 0) for g in games),
            "game_bytes_label": format_size(sum(g.get("size_bytes", 0) for g in games)),
            "install_report_present": bool(load_json(INSTALL_REPORT, {}).get("items", {})),
            "install_report_count": len(load_json(INSTALL_REPORT, {}).get("items", {})),
            "active_process_count": sum(1 for item in processes if item.get("status") == "running"),
            "process_count": len(processes), "max_active_environments": MAX_ACTIVE_ENVIRONMENTS,
            "games_limit_reached": len(games) >= MAX_GAMES,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "security": {
                "game_mount": "per-environment read-only bind mounts",
                "cross_environment_storage": "denied by default",
                "network_isolation": "one private bridge per environment; agents cannot reach sibling agents",
                "docker_socket_mounted": False, "privileged": False,
                "bind_address": "dashboard published only on 127.0.0.1",
            },
        }
    ready = 0
    needs_attention = 0
    for item in entries:
        status, _binary = status_fn(item)
        if status in ("AVAILABLE", "AVAILABLE VIA WINE"):
            ready += 1
        elif status not in ("NO LINUX EMULATOR BIN", "NO STANDALONE RUNNER", "UNVERIFIED VARIANT"):
            needs_attention += 1
    games = get_game_files()
    report = load_json(INSTALL_REPORT, {})
    report_items = report.get("items", {}) if isinstance(report, dict) else {}
    return {
        "project": "EmuStack", "version": "0.7.1", "emulator_count": len(entries),
        "launchers_ready": ready, "needs_attention": needs_attention,
        "game_count": len(games), "game_bytes": sum(g.get("size_bytes", 0) for g in games),
        "game_bytes_label": format_size(sum(g.get("size_bytes", 0) for g in games)),
        "install_report_present": bool(report_items), "install_report_count": len(report_items),
        "active_process_count": sum(1 for item in _process_snapshots() if item["status"] == "running"),
        "process_count": len(_process_snapshots()), "games_limit_reached": len(games) >= MAX_GAMES,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "security": {"game_mount": "read-only", "bind_address": "loopback only on host", "privileged": False},
    }

def format_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def summarize(catalog_fn: Callable[[], dict[str, Any]], status_fn: Callable[[dict[str, Any]], tuple[str, str | None]]) -> dict[str, Any]:
    entries = catalog_fn().get("emulators", [])
    ready = 0
    needs_attention = 0
    for item in entries:
        status, _binary = status_fn(item)
        if status in ("AVAILABLE", "AVAILABLE VIA WINE"):
            ready += 1
        elif status not in ("NO LINUX EMULATOR BIN", "NO STANDALONE RUNNER", "UNVERIFIED VARIANT"):
            needs_attention += 1
    games = get_game_files()
    report = load_json(INSTALL_REPORT, {})
    report_items = report.get("items", {}) if isinstance(report, dict) else {}
    return {
        "project": "EmuStack",
        "version": "0.7.1",
        "emulator_count": len(entries),
        "launchers_ready": ready,
        "needs_attention": needs_attention,
        "game_count": len(games),
        "game_bytes": sum(g.get("size_bytes", 0) for g in games),
        "game_bytes_label": format_size(sum(g.get("size_bytes", 0) for g in games)),
        "install_report_present": bool(report_items),
        "install_report_count": len(report_items),
        "active_process_count": sum(1 for item in _process_snapshots() if item["status"] == "running"),
        "process_count": len(_process_snapshots()),
        "games_limit_reached": len(games) >= MAX_GAMES,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "security": {"game_mount": "read-only", "bind_address": "loopback only on host", "privileged": False},
    }


def _start_managed_process(args: list[str], emulator_id: str, emulator_name: str, game: str | None = None) -> tuple[int, dict[str, Any]]:
    """Launch an allowlisted argument vector and track its process/log lifecycle."""
    global LAUNCH_RESERVATIONS
    with PROCESS_LOCK:
        active_count = sum(1 for rec in PROCESS_REGISTRY.values() if rec["process"].poll() is None)
        if active_count + LAUNCH_RESERVATIONS >= MAX_ACTIVE_PROCESSES:
            return 429, {"started": False, "error": f"Limite de sessões ativas atingido ({MAX_ACTIVE_PROCESSES}). Encerre uma sessão antes de iniciar outra."}
        LAUNCH_RESERVATIONS += 1
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        log_path = LOG_DIR / f"{emulator_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}.log"
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        _prune_log_files()
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True, bufsize=0)
    except OSError as exc:
        with PROCESS_LOCK:
            LAUNCH_RESERVATIONS = max(0, LAUNCH_RESERVATIONS - 1)
        return 500, {"started": False, "error": f"Falha ao iniciar processo: {exc}"}
    record = {
        "process": process,
        "emulator": emulator_id,
        "emulator_name": emulator_name,
        "game": game,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "log_path": str(log_path),
    }
    with PROCESS_LOCK:
        LAUNCH_RESERVATIONS = max(0, LAUNCH_RESERVATIONS - 1)
        PROCESS_REGISTRY[int(process.pid)] = record
        _prune_process_registry()
    capture_thread = threading.Thread(target=_capture_process_output, args=(process, log_path), daemon=True, name=f"emustack-log-{process.pid}")
    capture_thread.start()
    record["capture_thread"] = capture_thread
    time.sleep(0.15)
    exit_code = process.poll()
    if exit_code is not None:
        capture_thread.join(timeout=0.25)
        log_text, truncated = _read_log_tail(log_path)
        return 502, {
            "started": False,
            "error": "O launcher terminou imediatamente; consulte a saída capturada.",
            "pid": int(process.pid),
            "exit_code": exit_code,
            "log": log_text,
            "log_truncated": truncated,
            "message": "O launcher terminou imediatamente; consulte a saída capturada.",
        }
    return 202, {"started": True, "pid": int(process.pid), "emulator": emulator_id, "game": game, "status": "running"}


def make_handler(catalog_fn, status_fn, safe_game_path_fn):
    class Handler(BaseHTTPRequestHandler):
        server_version = "EmuStackDashboard/0.7.1"
        sys_version = ""

        def log_message(self, fmt, *args):
            sys.stderr.write("[EmuStack web] %s - %s\n" % (self.address_string(), fmt % args))

        def _send_bytes(self, data: bytes, content_type: str, status: int = 200, extra_headers: dict[str, str] | None = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
            self.send_header("Cache-Control", "no-store")
            if extra_headers:
                for key, value in extra_headers.items():
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def _json(self, data: Any, status: int = 200):
            self._send_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

        def _error(self, message: str, status: int = 400):
            self._json({"error": message}, status)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            # Agents share a network with this service so that the dashboard can
            # reach them; do not let an agent use that route to read other environments.
            if not _is_trusted_dashboard_client(self.client_address[0]):
                if path == "/api/health":
                    self._json({"healthy": True})
                else:
                    self._error("Acesso recusado: origem de rede não confiável.", 403)
                return
            if path == "/api/health":
                self._json(summarize(catalog_fn, status_fn))
                return
            if path == "/api/environments":
                records = environment_records(catalog_fn(), status_fn)
                self._json({"version": "0.7.1", "policy": "DENY_CROSS_ENVIRONMENT_STORAGE", "count": len(records), "online": sum(1 for x in records if x.get("online")), "environments": records})
                return
            if path == "/api/console-systems":
                try:
                    systems_payload = console_modes.load_systems(SYSTEMS_PATH)
                    resolved = _resolved_console_systems(catalog_fn, status_fn)
                    self._json({"schema_version": systems_payload.get("schema_version", 1), "version": "0.7.1", "systems": resolved})
                except RuntimeError as exc:
                    self._error(str(exc), 500)
                return
            if path == "/api/catalog":
                data = catalog_fn()
                items = []
                if ISOLATED_MODE:
                    envs_by_id = {env["id"]: env for env in environment_records(data, status_fn)}
                else:
                    envs_by_id = {}
                for item in data.get("emulators", []):
                    if ISOLATED_MODE:
                        status, binary = ("AGENT_MODE", None)
                    else:
                        status, binary = status_fn(item)
                    clone = dict(item)
                    env = envs_by_id.get(item.get("id"))
                    if ISOLATED_MODE:
                        clone["runtime_status"] = env.get("runtime_status", "AGENT_OFFLINE") if env else "AGENT_OFFLINE"
                        clone["binary_found"] = bool(env and env.get("binary_found"))
                        clone["binary_name"] = env.get("binary_name") if env else None
                        clone["environment_online"] = bool(env and env.get("online"))
                        clone["environment_id"] = item.get("id")
                    else:
                        clone["runtime_status"] = status
                        clone["binary_found"] = bool(binary)
                        clone["binary_name"] = Path(binary).name if binary else None
                        clone["environment_online"] = None
                        clone["environment_id"] = item.get("id")
                    clone["launchable"] = bool(clone["binary_found"]) and item.get("game_arg") != "blocked" and (clone["environment_online"] is not False)
                    if item.get("game_arg") == "blocked":
                        clone["launch_reason"] = item.get("notes", "Este projeto não possui lançador disponível.")
                    elif ISOLATED_MODE and not clone["environment_online"]:
                        clone["launch_reason"] = "O contêiner isolado deste emulador está offline."
                    items.append(clone)
                self._json({"schema_version": data.get("schema_version", 1), "version": "0.7.1", "emulators": items})
                return
            if path == "/api/processes":
                processes = _agent_processes()
                self._json({"processes": processes, "active": sum(1 for item in processes if item["status"] == "running")})
                return
            if path.startswith("/api/processes/") and path.endswith("/log"):
                pieces = path.strip("/").split("/")
                if ISOLATED_MODE:
                    if len(pieces) != 5 or pieces[0:2] != ["api", "processes"] or pieces[4] != "log" or not re.fullmatch(r"[a-f0-9]{32}", pieces[3]):
                        self._error("Identificador de sessão inválido", 400)
                        return
                    result = _agent_request(pieces[2], f"/processes/{pieces[3]}/log", None, 1.2)
                    if not result:
                        self._error("Ambiente indisponível ao buscar o log.", 503)
                    else:
                        self._json(result[1], result[0])
                    return
                if len(pieces) != 4 or pieces[0:2] != ["api", "processes"] or pieces[3] != "log" or not pieces[2].isdigit():
                    self._error("Identificador de processo inválido", 400)
                    return
                pid = int(pieces[2])
                with PROCESS_LOCK:
                    record = PROCESS_REGISTRY.get(pid)
                if record is None:
                    self._error("Sessão não encontrada neste processo do dashboard", 404)
                    return
                log_text, truncated = _read_log_tail(Path(record["log_path"]))
                self._json({"pid": pid, "log": log_text, "truncated": truncated, "status": _process_state(record)})
                return
            if path == "/api/games":
                games = get_game_files()
                self._json({"games": games, "count": len(games), "limit": MAX_GAMES, "limit_reached": len(games) >= MAX_GAMES})
                return
            if path == "/api/sources":
                sources = load_json(SOURCES_PATH, {"categories": [], "sources": []})
                self._json(sources)
                return
            if path == "/api/report":
                report = load_json(INSTALL_REPORT, None)
                if report is None:
                    self._json({"available": False, "message": "Relatório de build/instalação não encontrado; faça o build da imagem."}, 200)
                else:
                    self._json({"available": True, "report": report})
                return
            if path == "/api/docs":
                docs = []
                for doc_path in sorted(DOCS_DIR.glob("*.md")):
                    if doc_path.is_file() and not doc_path.is_symlink():
                        title_overrides = {"ORIGINAL_SYSTEM_UI": "Interfaces originais dos consoles"}
                        docs.append({"id": doc_path.stem, "title": title_overrides.get(doc_path.stem, doc_path.stem.replace("-", " ").replace("_", " ").title()), "filename": doc_path.name, "content": doc_path.read_text(encoding="utf-8")})
                readme = ROOT / "README.md"
                if readme.exists():
                    docs.insert(0, {"id": "readme", "title": "Visão geral", "filename": "README.md", "content": readme.read_text(encoding="utf-8")})
                self._json({"documents": docs})
                return
            if path == "/" or path == "/index.html":
                return self._static("index.html")
            if path.startswith("/assets/"):
                return self._static(path.removeprefix("/assets/"))
            if path == "/favicon.svg":
                return self._static("favicon.svg")
            self._error("Rota não encontrada", 404)

        def _static(self, relative: str):
            candidate = (WEB_DIR / relative).resolve()
            try:
                candidate.relative_to(WEB_DIR.resolve())
            except ValueError:
                self._error("Caminho inválido", 404)
                return
            if not candidate.is_file() or candidate.is_symlink():
                self._error("Arquivo não encontrado", 404)
                return
            mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            charset = "; charset=utf-8" if mime.startswith(("text/", "application/javascript", "image/svg+xml")) else ""
            self._send_bytes(candidate.read_bytes(), mime + charset)

        def _forward_launch(self, environment_id: str, route: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
            """Limit distinct active environments, while allowing sessions in an active one."""
            if environment_id not in _known_environment_ids():
                return 404, {"started": False, "error": "Ambiente não registrado no manifesto."}
            remote = _agent_processes()
            active_environment_ids = {
                str(item.get("environment_id")) for item in remote
                if item.get("status") == "running" and item.get("environment_id")
            }
            with PROCESS_LOCK:
                reserved_environment_ids = {eid for eid, count in ACTIVE_ENVIRONMENT_RESERVATIONS.items() if count > 0}
                occupied = active_environment_ids | reserved_environment_ids
                if environment_id not in occupied and len(occupied) >= MAX_ACTIVE_ENVIRONMENTS:
                    return 429, {"started": False, "error": f"Limite global de ambientes ativos atingido ({MAX_ACTIVE_ENVIRONMENTS}). Encerre uma sessão de outro console antes de abrir um novo ambiente."}
                ACTIVE_ENVIRONMENT_RESERVATIONS[environment_id] = ACTIVE_ENVIRONMENT_RESERVATIONS.get(environment_id, 0) + 1
            try:
                response = _agent_request(environment_id, route, payload, 3.0)
            finally:
                with PROCESS_LOCK:
                    remaining = ACTIVE_ENVIRONMENT_RESERVATIONS.get(environment_id, 1) - 1
                    if remaining > 0:
                        ACTIVE_ENVIRONMENT_RESERVATIONS[environment_id] = remaining
                    else:
                        ACTIVE_ENVIRONMENT_RESERVATIONS.pop(environment_id, None)
            if not response:
                return 503, {"started": False, "error": f"O agente env-{environment_id} não respondeu."}
            return response[0], response[1]

        def do_POST(self):
            global LAUNCH_RESERVATIONS
            # Host/Origin/custom headers alone are spoofable by a container on one of
            # the agent networks. Bind mutations to loopback in host-native mode or to
            # the explicitly allowlisted Docker bridge gateway IPs in Compose mode.
            if not _is_trusted_dashboard_client(self.client_address[0]):
                self._error("Requisição de controle recusada: origem de rede não confiável.", 403)
                return
            # This server is intended to be reachable only via the loopback-published host port.
            host_header = self.headers.get("Host", "")
            try:
                parsed_host = urlparse(f"http://{host_header}")
                host_is_local = parsed_host.hostname in {"127.0.0.1", "localhost", "::1"} and parsed_host.port is not None
            except ValueError:
                host_is_local = False
            if not host_is_local:
                self._error("A interface só aceita Host local. Acesse http://127.0.0.1:8765.", 403)
                return
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != host_header:
                self._error("Origem diferente da interface local recusada.", 403)
                return
            if self.headers.get("X-EmuStack-Request") != "1":
                self._error("Requisição não reconhecida; use a interface local.", 403)
                return
            length_text = self.headers.get("Content-Length", "0")
            try:
                length = int(length_text)
            except ValueError:
                self._error("Content-Length inválido")
                return
            if length < 1 or length > MAX_REQUEST:
                self._error("Corpo ausente ou grande demais", 413)
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._error("JSON inválido")
                return
            if not isinstance(payload, dict):
                self._error("O corpo JSON precisa ser um objeto.", 400)
                return

            route = urlparse(self.path).path
            if route == "/api/processes/stop":
                if ISOLATED_MODE:
                    environment_id = payload.get("environment_id")
                    session_id = payload.get("session_id")
                    if not isinstance(environment_id, str) or not isinstance(session_id, str) or not re.fullmatch(r"[a-f0-9]{32}", session_id):
                        self._error("Ambiente ou identificador de sessão inválido.", 400)
                        return
                    result = _agent_request(environment_id, "/processes/stop", {"session_id": session_id}, 2.5)
                    if not result:
                        self._error("Ambiente isolado indisponível para encerrar a sessão.", 503)
                    else:
                        self._json(result[1], result[0])
                    return
                pid_value = payload.get("pid")
                if isinstance(pid_value, bool) or not isinstance(pid_value, int) or pid_value <= 1:
                    self._error("PID inválido", 400)
                    return
                with PROCESS_LOCK:
                    record = PROCESS_REGISTRY.get(pid_value)
                if record is None:
                    self._error("Sessão não encontrada neste dashboard", 404)
                    return
                process = record["process"]
                if process.poll() is not None:
                    self._json({"stopped": False, "message": "O processo já terminou.", "process": _public_process(record)}, 409)
                    return
                # Track user-requested stops separately from crashes/non-zero exits so the
                # session UI does not incorrectly label a successful stop as a failure.
                record["stop_requested"] = True
                try:
                    # Every launcher is started in its own process group so a stop request
                    # also reaches the emulator child spawned by the CLI wrapper.
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                except OSError:
                    try:
                        process.terminate()
                    except OSError as exc:
                        self._error(f"Não foi possível encerrar o processo: {exc}", 500)
                        return
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except OSError:
                        try:
                            process.kill()
                        except OSError:
                            pass
                    try:
                        process.wait(timeout=1.0)
                    except (subprocess.TimeoutExpired, OSError):
                        pass
                stopped = process.poll() is not None
                self._json({"stopped": stopped, "process": _public_process(record)}, 200 if stopped else 202)
                return

            if route == "/api/console-systems/launch":
                if ISOLATED_MODE:
                    system_id = payload.get("system")
                    action = payload.get("action", "boot")
                    if not isinstance(system_id, str) or len(system_id) > 80:
                        self._error("ID de sistema inválido", 400)
                        return
                    if action not in {"boot", "open"}:
                        self._error("Ação inválida; use boot ou open.", 400)
                        return
                    try:
                        profiles = _resolved_console_systems(catalog_fn, status_fn)
                    except RuntimeError as exc:
                        self._error(str(exc), 500)
                        return
                    profile = next((entry for entry in profiles if entry.get("id") == system_id), None)
                    if profile is None:
                        self._error("Sistema não reconhecido", 404)
                        return
                    if action == "boot" and not profile.get("can_boot_original"):
                        self._json({
                            "error": "O boot automático da interface original não está disponível neste momento.",
                            "state": profile.get("state"), "state_label": profile.get("state_label"),
                            "details": profile.get("details"), "checks": profile.get("checks", []),
                            "setup_steps": profile.get("setup_steps", []),
                        }, 409)
                        return
                    if action == "open" and not profile.get("can_open_emulator"):
                        self._error("Nenhum launcher disponível neste ambiente isolado.", 409)
                        return
                    environment_id = profile.get("environment_id") or (profile.get("emulator_ids") or [None])[0]
                    if not isinstance(environment_id, str):
                        self._error("Este perfil não tem um ambiente de execução associado.", 409)
                        return
                    status_code, result = self._forward_launch(environment_id, "/console-system", {"system": system_id, "action": action})
                    result["system"] = system_id
                    result["action"] = action
                    if action == "open":
                        result["details"] = profile.get("details", "")
                    self._json(result, status_code)
                    return
                system_id = payload.get("system")
                action = payload.get("action", "boot")
                if not isinstance(system_id, str) or len(system_id) > 80:
                    self._error("ID de sistema inválido", 400)
                    return
                try:
                    systems_payload = console_modes.load_systems(SYSTEMS_PATH)
                    resolved_systems = console_modes.resolve_systems(catalog_fn(), status_fn, systems_payload)
                except RuntimeError as exc:
                    self._error(str(exc), 500)
                    return
                profile = next((entry for entry in resolved_systems if entry.get("id") == system_id), None)
                if profile is None:
                    self._error("Sistema não reconhecido", 404)
                    return
                if not os.environ.get("DISPLAY"):
                    self._error("A sessão gráfica não está configurada. Rode host-setup numa sessão X11/XWayland e recrie os serviços gráficos.", 409)
                    return
                if action not in {"boot", "open"}:
                    self._error("Ação inválida; use boot ou open.", 400)
                    return
                if action == "boot":
                    if not profile.get("can_boot_original"):
                        self._json({
                            "error": "O boot automático da interface original não está disponível neste momento.",
                            "state": profile.get("state"),
                            "state_label": profile.get("state_label"),
                            "details": profile.get("details"),
                            "checks": profile.get("checks", []),
                            "setup_steps": profile.get("setup_steps", []),
                        }, 409)
                        return
                    command = [sys.executable, str(CLI_PATH), "boot-system", system_id]
                    launcher_id = next((eid for eid in profile.get("emulator_ids", []) if any(e.get("id") == eid and status_fn(e)[1] for e in catalog_fn().get("emulators", []))), profile.get("emulator_ids", [system_id])[0] if profile.get("emulator_ids") else system_id)
                    session_name = f"{profile.get('name', system_id)} — {profile.get('interface_name', 'sistema original')}"
                    session_game = f"Interface original: {profile.get('interface_name', profile.get('name', system_id))}"
                    response_instructions = []
                else:
                    if not profile.get("can_open_emulator"):
                        self._error("Nenhum launcher associado está disponível. Confira o catálogo e o relatório de instalação.", 409)
                        return
                    catalog_items = catalog_fn().get("emulators", [])
                    launcher_id = None
                    for candidate_id in profile.get("emulator_ids", []):
                        candidate = next((entry for entry in catalog_items if entry.get("id") == candidate_id), None)
                        if candidate and status_fn(candidate)[1]:
                            launcher_id = candidate_id
                            break
                    if not launcher_id:
                        self._error("Nenhum launcher associado foi encontrado.", 409)
                        return
                    command = [sys.executable, str(CLI_PATH), "launch", launcher_id]
                    candidate = next(entry for entry in catalog_items if entry.get("id") == launcher_id)
                    session_name = f"{profile.get('name', system_id)} — configuração do emulador"
                    session_game = None
                    response_instructions = profile.get("setup_steps", [])
                status_code, result = _start_managed_process(
                    command, launcher_id, session_name, session_game
                )
                result["system"] = system_id
                result["action"] = action
                result["instructions"] = response_instructions
                if action == "open":
                    result["details"] = profile.get("details", "")
                self._json(result, status_code)
                return

            if route != "/api/launch":
                self._error("Rota não encontrada", 404)
                return
            if ISOLATED_MODE:
                emulator_id = payload.get("emulator")
                game_rel = payload.get("game")
                if not isinstance(emulator_id, str) or len(emulator_id) > 80:
                    self._error("ID de emulador inválido", 400)
                    return
                item = next((entry for entry in catalog_fn().get("emulators", []) if entry.get("id") == emulator_id), None)
                if not item:
                    self._error("Emulador não reconhecido", 404)
                    return
                if item.get("game_arg") == "blocked":
                    self._error(item.get("notes", "Este projeto não possui um lançador compatível."), 409)
                    return
                if game_rel not in (None, "") and not isinstance(game_rel, str):
                    self._error("Caminho de jogo inválido", 400)
                    return
                if isinstance(game_rel, str) and len(game_rel) > 1024:
                    self._error("Caminho de jogo inválido", 400)
                    return
                if emulator_id == "rpcs3" and isinstance(game_rel, str) and Path(game_rel).suffix.lower() in {".rap", ".edat"}:
                    self._error("RAP/EDAT é dado de licença/suporte, não um jogo inicializável.", 400)
                    return
                result = _agent_request(emulator_id, "/health", None, 1.0)
                if not result or result[0] != 200 or not result[1].get("healthy"):
                    self._error(f"Ambiente isolado env-{emulator_id} indisponível. Inicie/recrie os serviços com Docker Compose.", 503)
                    return
                if not result[1].get("binary_found"):
                    self._error(f"Launcher não disponível no ambiente {emulator_id}: {result[1].get('runtime_status', 'indisponível')}.", 409)
                    return
                status_code, launch_result = self._forward_launch(emulator_id, "/launch", {"game": game_rel or ""})
                self._json(launch_result, status_code)
                return
            emulator_id = payload.get("emulator")
            game_rel = payload.get("game")
            if not isinstance(emulator_id, str) or len(emulator_id) > 80:
                self._error("ID de emulador inválido", 400)
                return
            all_items = catalog_fn().get("emulators", [])
            item = next((entry for entry in all_items if entry.get("id") == emulator_id), None)
            if not item:
                self._error("Emulador não reconhecido", 404)
                return
            if item.get("game_arg") == "blocked":
                self._error(item.get("notes", "Este projeto não possui um lançador compatível."), 409)
                return
            status, binary = status_fn(item)
            if not binary:
                self._error(f"Lançador não disponível: {status}. Confira o relatório de instalação.", 409)
                return
            if not os.environ.get("DISPLAY"):
                self._error("A sessão gráfica não está configurada. Rode host-setup numa sessão X11/XWayland e recrie o override para iniciar emuladores gráficos.", 409)
                return
            if game_rel not in (None, "") and not isinstance(game_rel, str):
                self._error("Caminho de jogo inválido", 400)
                return
            if isinstance(game_rel, str) and len(game_rel) > 1024:
                self._error("Caminho de jogo inválido", 400)
                return
            if item.get("game_arg") == "ui-only" and game_rel:
                self._error("Este emulador escolhe o conteúdo dentro da própria interface; não passe um arquivo neste formulário.", 400)
                return
            if emulator_id == "rpcs3" and isinstance(game_rel, str) and Path(game_rel).suffix.lower() in {".rap", ".edat"}:
                self._error("Arquivo de licença/suporte não é um jogo inicializável. Abra RPCS3 e use a interface de instalação/gestão de licenças.", 400)
                return
            resolved_game: str | None = None
            if game_rel:
                try:
                    game_path = safe_game_path_fn(game_rel)
                except SystemExit as exc:
                    self._error(str(exc), 400)
                    return
                if not game_path.is_file():
                    self._error("O caminho selecionado não é um arquivo regular.", 400)
                    return
                resolved_game = str(game_path)
            args = [sys.executable, str(CLI_PATH), "launch", emulator_id]
            if resolved_game:
                args.append(resolved_game)
            status_code, result = _start_managed_process(args, emulator_id, item.get("name", emulator_id), resolved_game)
            self._json(result, status_code)

        def do_HEAD(self):
            if not _is_trusted_dashboard_client(self.client_address[0]):
                self.send_response(403)
                self.end_headers()
                return
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

    return Handler


def serve(host: str, port: int, catalog_fn, status_fn, safe_game_path_fn) -> int:
    handler = make_handler(catalog_fn, status_fn, safe_game_path_fn)
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    print(f"EmuStack Dashboard 0.7.1 ouvindo em http://{host}:{port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
