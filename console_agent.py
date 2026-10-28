#!/usr/bin/env python3
"""Isolated per-emulator agent. Runs inside one console environment container.

The agent exposes a small allowlisted HTTP API only on the Compose network. It
never accepts commands, binary paths, or arbitrary arguments from the dashboard.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlparse
from typing import Any

import console_modes
import emustack

ROOT = Path(__file__).resolve().parent
CATALOG_PATH = Path(os.environ.get("EMUSTACK_CATALOG", str(ROOT / "catalog.json")))
SYSTEMS_PATH = Path(os.environ.get("EMUSTACK_SYSTEMS_PATH", str(ROOT / "console-systems.json")))
ENVIRONMENTS_PATH = Path(os.environ.get("EMUSTACK_ENVIRONMENTS_PATH", str(ROOT / "environments.json")))
ENV_ID = os.environ.get("EMUSTACK_ENV_ID", "").strip()
AGENT_PORT = int(os.environ.get("EMUSTACK_AGENT_PORT", "8877"))
AGENT_TOKEN = os.environ.get("EMUSTACK_AGENT_TOKEN", "")
GAMES_DIR = Path(os.environ.get("EMUSTACK_GAMES_DIR", "/games")).resolve()
LOG_DIR = Path(os.environ.get("EMUSTACK_LOG_DIR", "/home/emu/.local/state/emustack/logs")).resolve()
MAX_REQUEST = 16 * 1024
MAX_GAMES = 3000
MAX_ACTIVE_PER_ENV = int(os.environ.get("EMUSTACK_MAX_ACTIVE_PER_ENV", "2"))
MAX_RETAINED_LOG_FILES = 100
MAX_PROCESS_LOG_BYTES = 128 * 1024


def _format_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
_LOCK = threading.RLock()
_SESSIONS: dict[str, dict[str, Any]] = {}


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _catalog() -> dict[str, Any]:
    payload = _load_json(CATALOG_PATH, {})
    if payload.get("schema_version") != 1 or not isinstance(payload.get("emulators"), list):
        raise RuntimeError("Catálogo de emuladores inválido.")
    return payload


def _systems() -> dict[str, Any]:
    return console_modes.load_systems(SYSTEMS_PATH)


def _manifest() -> dict[str, Any]:
    payload = _load_json(ENVIRONMENTS_PATH, {})
    if payload.get("schema_version") != 1 or not isinstance(payload.get("environments"), list):
        raise RuntimeError("Manifesto environments.json inválido.")
    return payload


def _profile() -> dict[str, Any]:
    matches = [x for x in _manifest()["environments"] if x.get("id") == ENV_ID]
    if len(matches) != 1:
        raise RuntimeError(f"EMUSTACK_ENV_ID inválido ou ausente: {ENV_ID!r}")
    return matches[0]


def _emulator() -> dict[str, Any]:
    matches = [x for x in _catalog()["emulators"] if x.get("id") == ENV_ID]
    if len(matches) != 1:
        raise RuntimeError(f"Emulador associado ao ambiente não existe no catálogo: {ENV_ID!r}")
    return matches[0]


def _runtime() -> tuple[str, str | None]:
    return emustack.runtime_status(_emulator())


def _resolve_system_for_this_environment(profile: dict[str, Any]) -> dict[str, Any]:
    """Resolve a system against this agent's emulator only, not sibling variants."""
    if ENV_ID not in profile.get("emulator_ids", []):
        raise ValueError("Este sistema não está associado a este ambiente.")
    own_profile = dict(profile)
    own_profile["emulator_ids"] = [ENV_ID]
    own_catalog = dict(_catalog())
    own_catalog["emulators"] = [_emulator()]
    resolved = console_modes.resolve_systems(
        own_catalog,
        emustack.runtime_status,
        {"schema_version": 1, "systems": [own_profile]},
    )
    if not resolved:
        raise RuntimeError("Não foi possível resolver o perfil deste ambiente.")
    return resolved[0]


def _status_label(status: str, binary: str | None) -> str:
    return f"{status}: {Path(binary).name}" if binary else status


def _safe_relative_game(raw: str) -> tuple[Path, str]:
    if not isinstance(raw, str) or not raw or len(raw) > 1024 or "\x00" in raw or "\\" in raw:
        raise ValueError("Caminho de jogo inválido.")
    rel = PurePosixPath(raw)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ValueError("O jogo deve ser selecionado por um caminho relativo dentro deste ambiente.")
    candidate = GAMES_DIR.joinpath(*rel.parts)
    try:
        # Refuse symlinks in every component, even when they resolve inside /games.
        current = GAMES_DIR
        for part in rel.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("Links simbólicos não são aceitos na biblioteca do ambiente.")
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(GAMES_DIR.resolve())
    except ValueError:
        raise
    except (OSError, RuntimeError) as exc:
        raise ValueError("Arquivo não encontrado ou caminho inválido neste ambiente.") from exc
    if not resolved.is_file() or not candidate.is_file():
        raise ValueError("O caminho selecionado não é um arquivo regular.")
    return resolved, rel.as_posix()


def _game_files() -> list[dict[str, Any]]:
    extensions = {
        ".iso", ".cso", ".chd", ".cue", ".bin", ".img", ".mdf", ".pbp", ".pkg", ".elf", ".self",
        ".gcm", ".rvz", ".wbfs", ".wud", ".wux", ".wua", ".nsp", ".xci", ".nro", ".3ds", ".cci",
        ".cia", ".nds", ".gba", ".gbc", ".gb", ".nes", ".sfc", ".smc", ".n64", ".z64", ".v64",
        ".pce", ".32x", ".md", ".gen", ".sms", ".gg", ".a26", ".a52", ".lnx", ".tap", ".d64",
        ".adf", ".wad", ".dol", ".gcz", ".ciso", ".wii", ".xex", ".xcp",
    }
    games: list[dict[str, Any]] = []
    if not GAMES_DIR.is_dir():
        return games
    try:
        paths = GAMES_DIR.rglob("*")
        for path in paths:
            if len(games) >= MAX_GAMES:
                break
            try:
                rel = path.relative_to(GAMES_DIR)
                if path.is_symlink() or not path.is_file() or any(part.startswith(".") for part in rel.parts):
                    continue
                if path.suffix.lower() not in extensions:
                    continue
                stat = path.stat()
                games.append({
                    "path": rel.as_posix(), "name": path.name, "extension": path.suffix.lower(),
                    "size_bytes": stat.st_size, "size_label": _format_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    "environment_id": ENV_ID,
                })
            except (OSError, ValueError):
                continue
    except OSError:
        return []
    games.sort(key=lambda item: item["path"].casefold())
    return games


def _capture_output(process: subprocess.Popen[bytes], log_path: Path) -> None:
    stream = process.stdout
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
        pass
    finally:
        try:
            stream.close()
        except (OSError, AttributeError):
            pass


def _session_status(record: dict[str, Any]) -> str:
    process = record["process"]
    if process.poll() is None:
        return "running"
    if record.get("stop_requested"):
        return "stopped"
    return "exited" if process.returncode == 0 else "failed"


def _public_session(session_id: str, record: dict[str, Any]) -> dict[str, Any]:
    proc = record["process"]
    return {
        "session_id": session_id, "environment_id": ENV_ID, "pid": int(proc.pid),
        "emulator": ENV_ID, "emulator_name": record["emulator_name"], "game": record.get("game"),
        "started_at": record["started_at"], "status": _session_status(record),
        "exit_code": proc.returncode, "log_available": Path(record["log_path"]).is_file(),
    }


def _sessions() -> list[dict[str, Any]]:
    with _LOCK:
        items = [(_sid, _public_session(_sid, rec)) for _sid, rec in _SESSIONS.items()]
    return sorted((item for _sid, item in items), key=lambda item: item["started_at"], reverse=True)


def _read_log(path: Path) -> tuple[str, bool]:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            truncated = size > MAX_PROCESS_LOG_BYTES
            handle.seek(max(0, size - MAX_PROCESS_LOG_BYTES), os.SEEK_SET)
            raw = handle.read(MAX_PROCESS_LOG_BYTES)
        return raw.decode("utf-8", errors="replace"), truncated
    except OSError:
        return "Log ainda não disponível.", False


def _prune_logs() -> None:
    try:
        logs = sorted((p for p in LOG_DIR.glob("*.log") if p.is_file() and not p.is_symlink()), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    for path in logs[MAX_RETAINED_LOG_FILES:]:
        try:
            path.unlink()
        except OSError:
            pass


def _start(args: list[str], display_name: str, game_label: str | None) -> tuple[int, dict[str, Any]]:
    with _LOCK:
        running = sum(1 for rec in _SESSIONS.values() if rec["process"].poll() is None)
        if running >= MAX_ACTIVE_PER_ENV:
            return 429, {"started": False, "error": f"Limite por ambiente atingido ({MAX_ACTIVE_PER_ENV} sessões)."}
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        session_id = uuid.uuid4().hex
        log_path = LOG_DIR / f"{ENV_ID}-{int(time.time())}-{session_id[:8]}.log"
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        _prune_logs()
        process = subprocess.Popen(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True, bufsize=0,
        )
    except OSError as exc:
        return 500, {"started": False, "error": f"Falha ao iniciar o launcher isolado: {exc}"}
    record = {
        "process": process, "emulator_name": display_name, "game": game_label,
        "started_at": datetime.now(timezone.utc).isoformat(), "log_path": str(log_path),
    }
    with _LOCK:
        _SESSIONS[session_id] = record
        if len(_SESSIONS) > 100:
            completed = [(sid, item) for sid, item in _SESSIONS.items() if item["process"].poll() is not None]
            completed.sort(key=lambda pair: pair[1]["started_at"])
            for sid, old in completed[: max(0, len(_SESSIONS) - 100)]:
                _SESSIONS.pop(sid, None)
                try:
                    Path(old["log_path"]).unlink(missing_ok=True)
                except OSError:
                    pass
    threading.Thread(target=_capture_output, args=(process, log_path), daemon=True, name=f"emustack-log-{process.pid}").start()
    time.sleep(0.12)
    exit_code = process.poll()
    if exit_code is not None:
        log_text, truncated = _read_log(log_path)
        return 502, {
            "started": False, "error": "O launcher terminou imediatamente; consulte o log do ambiente.",
            "session_id": session_id, "pid": process.pid, "exit_code": exit_code,
            "log": log_text, "log_truncated": truncated,
        }
    return 202, {"started": True, "session_id": session_id, "pid": int(process.pid), "environment_id": ENV_ID, "status": "running"}


def _start_emulator(game: str | None = None) -> tuple[int, dict[str, Any]]:
    item = _emulator()
    status, binary = _runtime()
    if item.get("game_arg") == "blocked":
        return 409, {"started": False, "error": item.get("notes", "Este projeto não possui runner suportado.")}
    if not binary:
        return 409, {"started": False, "error": f"Launcher indisponível: {_status_label(status, binary)}. Confira o relatório de instalação."}
    if not os.environ.get("DISPLAY"):
        return 409, {"started": False, "error": "DISPLAY não está configurado neste ambiente. Rode host-setup numa sessão X11/XWayland para habilitar apps gráficos."}
    selected_game: str | None = None
    if game:
        try:
            _path, selected_game = _safe_relative_game(game)
        except ValueError as exc:
            return 400, {"started": False, "error": str(exc)}
        if item.get("game_arg") == "ui-only":
            return 400, {"started": False, "error": "Este emulador escolhe o conteúdo pela própria interface e não aceita arquivo neste formulário."}
        if ENV_ID == "rpcs3" and Path(selected_game).suffix.lower() in {".rap", ".edat"}:
            return 400, {"started": False, "error": "RAP/EDAT é dado de licença/suporte, não um jogo inicializável."}
    args = [sys.executable, str(ROOT / "emustack.py"), "launch", ENV_ID]
    if selected_game:
        args.append(selected_game)
    display_name = item.get("name", ENV_ID)
    return _start(args, display_name, selected_game)


def _start_system(system_id: str, action: str) -> tuple[int, dict[str, Any]]:
    try:
        systems_payload = _systems()
    except RuntimeError as exc:
        return 500, {"started": False, "error": str(exc)}
    profile = next((p for p in systems_payload["systems"] if p.get("id") == system_id), None)
    if not profile:
        return 404, {"started": False, "error": "Sistema não reconhecido."}
    if ENV_ID not in profile.get("emulator_ids", []):
        return 403, {"started": False, "error": "Este ambiente não é autorizado para iniciar esse perfil de sistema."}
    state = _resolve_system_for_this_environment(profile)
    if action == "boot":
        if not state or not state.get("can_boot_original"):
            checks = (state or {}).get("checks", [])
            detail = "\n".join(f"- {x.get('label')}: {x.get('detail')}" for x in checks)
            return 409, {
                "started": False, "error": "O boot do sistema original não está disponível neste ambiente.",
                "state": (state or {}).get("state"), "state_label": (state or {}).get("state_label"),
                "details": (state or {}).get("details"), "checks": checks, "setup_steps": (state or {}).get("setup_steps", []),
                "diagnostic": detail,
            }
        if not os.environ.get("DISPLAY"):
            return 409, {"started": False, "error": "DISPLAY não configurado no ambiente isolado."}
        cmd = [sys.executable, str(ROOT / "emustack.py"), "boot-system", system_id]
        name = f"{profile.get('name', system_id)} — {profile.get('interface_name', 'sistema original')}"
        session_game = f"Sistema original: {profile.get('interface_name', profile.get('name', system_id))}"
    elif action == "open":
        item = _emulator()
        status, binary = _runtime()
        if not binary or item.get("game_arg") == "blocked":
            return 409, {"started": False, "error": f"Launcher não disponível: {_status_label(status, binary)}."}
        if not os.environ.get("DISPLAY"):
            return 409, {"started": False, "error": "DISPLAY não configurado no ambiente isolado."}
        cmd = [sys.executable, str(ROOT / "emustack.py"), "launch", ENV_ID]
        name = f"{profile.get('name', system_id)} — configuração do emulador"
        session_game = None
    else:
        return 400, {"started": False, "error": "Ação inválida; use boot ou open."}
    status_code, result = _start(cmd, name, session_game)
    result.update({"system": system_id, "action": action, "instructions": profile.get("setup_steps", []) if action == "open" else []})
    if action == "open":
        result["details"] = profile.get("details", "")
    return status_code, result


class AgentHandler(BaseHTTPRequestHandler):
    server_version = "EmuStackConsoleAgent/0.7.1"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"[EmuStack agent {ENV_ID}] {self.address_string()} - {fmt % args}\n")

    def _send(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        supplied = self.headers.get("X-EmuStack-Agent-Token", "")
        # Constant-time comparison avoids a byte-by-byte secret comparison.
        import hmac
        okay = bool(AGENT_TOKEN) and hmac.compare_digest(supplied, AGENT_TOKEN)
        if not okay:
            self._send({"error": "Autenticação do agente recusada."}, 403)
        return okay

    def _json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send({"error": "Content-Length inválido."}, 400)
            return None
        if length < 1 or length > MAX_REQUEST:
            self._send({"error": "Corpo ausente ou grande demais."}, 413)
            return None
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send({"error": "JSON inválido."}, 400)
            return None
        if not isinstance(payload, dict):
            self._send({"error": "O corpo JSON precisa ser um objeto."}, 400)
            return None
        return payload

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            if not AGENT_TOKEN:
                self._send({"healthy": False, "error": "EMUSTACK_AGENT_TOKEN não configurado."}, 503)
                return
            try:
                profile = _profile()
                status, binary = _runtime()
                self._send({
                    "healthy": True, "version": "0.7.1", "environment_id": ENV_ID,
                    "emulator_id": ENV_ID, "environment_name": profile.get("name"),
                    "runtime_status": status, "binary_found": bool(binary),
                    "binary_name": Path(binary).name if binary else None,
                    "active_sessions": sum(1 for item in _sessions() if item["status"] == "running"),
                    "data_isolation": "per-environment bind mounts; no shared game/BIOS/save/config mount",
                })
            except Exception as exc:
                self._send({"healthy": False, "error": str(exc)}, 503)
            return
        if not self._authorized():
            return
        if parsed.path == "/games":
            games = _game_files()
            self._send({"environment_id": ENV_ID, "games": games, "count": len(games), "limit_reached": len(games) >= MAX_GAMES})
            return
        if parsed.path == "/processes":
            items = _sessions()
            self._send({"environment_id": ENV_ID, "processes": items, "active": sum(1 for p in items if p["status"] == "running")})
            return
        if parsed.path.startswith("/processes/") and parsed.path.endswith("/log"):
            pieces = parsed.path.strip("/").split("/")
            if len(pieces) != 3 or not re.fullmatch(r"[a-f0-9]{32}", pieces[1]):
                self._send({"error": "Identificador de sessão inválido."}, 400)
                return
            with _LOCK:
                record = _SESSIONS.get(pieces[1])
            if record is None:
                self._send({"error": "Sessão não encontrada neste ambiente."}, 404)
                return
            log, truncated = _read_log(Path(record["log_path"]))
            self._send({"session_id": pieces[1], "environment_id": ENV_ID, "log": log, "truncated": truncated, "status": _session_status(record)})
            return
        if parsed.path == "/system-status":
            query = parse_qs(parsed.query)
            system_id = query.get("system", [""])[0]
            try:
                systems_payload = _systems()
                profile = next((p for p in systems_payload["systems"] if p.get("id") == system_id), None)
                if not profile or ENV_ID not in profile.get("emulator_ids", []):
                    self._send({"error": "Perfil não associado a este ambiente."}, 404)
                    return
                item = _resolve_system_for_this_environment(profile)
                item["environment_id"] = ENV_ID
                item["environment_online"] = True
                self._send(item)
            except Exception as exc:
                self._send({"error": f"Não foi possível resolver o estado do sistema: {exc}"}, 500)
            return
        self._send({"error": "Rota não encontrada."}, 404)

    def do_POST(self) -> None:
        if not self._authorized():
            return
        parsed = urlparse(self.path)
        payload = self._json_body()
        if payload is None:
            return
        if parsed.path == "/launch":
            game = payload.get("game", "")
            if game in (None, ""):
                game = None
            if not isinstance(game, str):
                self._send({"error": "Caminho de jogo inválido."}, 400)
                return
            status, result = _start_emulator(game)
            self._send(result, status)
            return
        if parsed.path == "/console-system":
            system_id = payload.get("system")
            action = payload.get("action", "boot")
            if not isinstance(system_id, str) or len(system_id) > 80:
                self._send({"error": "ID de sistema inválido."}, 400)
                return
            if action not in {"boot", "open"}:
                self._send({"error": "Ação inválida; use boot ou open."}, 400)
                return
            status, result = _start_system(system_id, action)
            self._send(result, status)
            return
        if parsed.path == "/processes/stop":
            session_id = payload.get("session_id")
            if not isinstance(session_id, str) or not re.fullmatch(r"[a-f0-9]{32}", session_id):
                self._send({"error": "Identificador de sessão inválido."}, 400)
                return
            with _LOCK:
                record = _SESSIONS.get(session_id)
            if record is None:
                self._send({"error": "Sessão não encontrada neste ambiente."}, 404)
                return
            proc = record["process"]
            if proc.poll() is not None:
                self._send({"stopped": False, "message": "A sessão já terminou.", "process": _public_session(session_id, record)}, 409)
                return
            record["stop_requested"] = True
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError:
                try:
                    proc.terminate()
                except OSError as exc:
                    self._send({"error": f"Não foi possível encerrar a sessão: {exc}"}, 500)
                    return
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    try:
                        proc.kill()
                    except OSError:
                        pass
                try:
                    proc.wait(timeout=1.0)
                except (subprocess.TimeoutExpired, OSError):
                    pass
            stopped = proc.poll() is not None
            self._send({"stopped": stopped, "process": _public_session(session_id, record)}, 200 if stopped else 202)
            return
        self._send({"error": "Rota não encontrada."}, 404)


def main() -> int:
    try:
        _profile()
        _emulator()
    except Exception as exc:
        print(f"ERRO: agente não pôde validar seu ambiente: {exc}", file=sys.stderr, flush=True)
        return 2
    if not AGENT_TOKEN:
        print("ERRO: EMUSTACK_AGENT_TOKEN ausente. Execute scripts/host-setup.sh.", file=sys.stderr, flush=True)
        return 2
    server = ThreadingHTTPServer(("0.0.0.0", AGENT_PORT), AgentHandler)
    server.daemon_threads = True
    print(f"EmuStack Agent 0.7.1: ambiente={ENV_ID}, porta interna={AGENT_PORT}", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
