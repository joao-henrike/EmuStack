"""Pure helpers for optional runtime probes; safe to unit-test without Docker."""
from __future__ import annotations

import os
from datetime import datetime
import re
from pathlib import Path
from typing import Mapping, Any

_TRUTHY = {"1", "true", "yes", "on"}
_SOFTWARE_VULKAN = re.compile(r"llvmpipe|lavapipe|swiftshader|softpipe|software rasterizer", re.I)
_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INPUT_DEVICE = re.compile(r"^/dev/input/(?:event|js)[0-9]+$")


def env_flag(name: str, environ: Mapping[str, str] | None = None) -> bool:
    """Parse an opt-in boolean without treating arbitrary non-empty text as true."""
    source = os.environ if environ is None else environ
    return source.get(name, "").strip().lower() in _TRUTHY


def parse_env_file(path: str | Path) -> dict[str, str]:
    """Read simple KEY=VALUE lines. Never evaluate shell syntax or interpolation."""
    values: dict[str, str] = {}
    source = Path(path)
    if not source.is_file():
        return values
    for raw in source.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not _KEY.fullmatch(key):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    return values


def is_software_vulkan_renderer(output: str) -> bool:
    return bool(_SOFTWARE_VULKAN.search(output or ""))


def is_dashboard_summary_response(
    status_code: int, payload: object, expected_profiles: int = 20
) -> bool:
    """Validate the trusted dashboard summary used by the bounded API smoke."""
    if status_code != 200 or not isinstance(payload, Mapping):
        return False
    if payload.get("project") != "EmuStack":
        return False
    count = payload.get("emulator_count")
    if type(count) is not int or count != expected_profiles:
        return False
    for field in ("launchers_ready", "needs_attention", "game_count", "game_bytes",
                  "active_process_count", "process_count", "install_report_count"):
        value = payload.get(field)
        if type(value) is not int or value < 0:
            return False
    if not isinstance(payload.get("generated_at"), str):
        return False
    try:
        datetime.fromisoformat(payload["generated_at"].replace("Z", "+00:00"))
    except ValueError:
        return False
    if not isinstance(payload.get("security"), Mapping):
        return False
    return True



def runtime_guardrail_issues(host_config: Mapping[str, Any]) -> list[str]:
    """Return missing or unbounded resource, restart, and log-rotation settings."""
    if not isinstance(host_config, Mapping):
        return ["Docker HostConfig is missing"]
    issues: list[str] = []
    memory = host_config.get("Memory")
    if type(memory) is not int or memory <= 0:
        issues.append("memory limit is missing or unbounded")
    nano_cpus = host_config.get("NanoCpus")
    cpu_quota = host_config.get("CpuQuota")
    cpu_period = host_config.get("CpuPeriod")
    finite_nano_cpus = type(nano_cpus) is int and nano_cpus > 0
    finite_quota = type(cpu_quota) is int and cpu_quota > 0 and type(cpu_period) is int and cpu_period > 0
    if not (finite_nano_cpus or finite_quota):
        issues.append("CPU limit is missing or unbounded")
    pids_limit = host_config.get("PidsLimit")
    if type(pids_limit) is not int or pids_limit <= 0:
        issues.append("PID limit is missing or unbounded")
    restart = host_config.get("RestartPolicy")
    if not isinstance(restart, Mapping) or restart.get("Name") != "unless-stopped":
        issues.append("restart policy is not unless-stopped")
    log_config = host_config.get("LogConfig")
    if not isinstance(log_config, Mapping) or log_config.get("Type") != "json-file":
        issues.append("logging driver is not json-file with rotation")
        return issues
    options = log_config.get("Config")
    if not isinstance(options, Mapping):
        options = {}
    max_size = str(options.get("max-size", "")).strip().lower()
    match = re.fullmatch(r"([1-9][0-9]*)([kmg]?)", max_size)
    if not match:
        issues.append("log max-size is missing or invalid")
    else:
        multiplier = {"": 1, "k": 1000, "m": 1000**2, "g": 1000**3}[match.group(2)]
        if int(match.group(1)) * multiplier > 1_000_000_000:
            issues.append("log max-size exceeds 1 GB")
    max_files = str(options.get("max-file", "")).strip()
    if not max_files.isdigit() or not 1 <= int(max_files) <= 100:
        issues.append("log max-file must be between 1 and 100")
    return issues


def is_allowed_input_device(path: str) -> bool:
    """Only accept the specific evdev/joystick nodes allowed by host-setup.sh."""
    return bool(_INPUT_DEVICE.fullmatch(path or ""))


def has_readonly_device_mapping(host_config: Mapping[str, Any], path: str) -> bool:
    """Require the exact host and container path plus read-only device permission."""
    for mapping in host_config.get("Devices", []) or []:
        host = str(mapping.get("PathOnHost", ""))
        container = str(mapping.get("PathInContainer", ""))
        permissions = str(mapping.get("CgroupPermissions", ""))
        if host == path and container == path and "r" in permissions and "w" not in permissions and "m" not in permissions:
            return True
    return False
