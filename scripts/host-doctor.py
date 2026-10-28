#!/usr/bin/env python3
"""Read-only host capability inventory; never changes devices or permissions."""
from __future__ import annotations
import json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def command_version(command: str, args: list[str]) -> dict:
    path = shutil.which(command)
    if not path: return {"available": False, "path": None, "version": None}
    try:
        result = subprocess.run([path, *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=8, check=False)
        line = next((x.strip() for x in result.stdout.splitlines() if x.strip()), "")
        return {"available": result.returncode == 0, "path": path, "version": line[:240]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "path": path, "version": None, "error": type(exc).__name__}

def main() -> int:
    uid = os.getuid()
    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid}"))
    dev_input = Path("/dev/input")
    host = {
      "schema_version": 1,
      "project": "EmuStack",
      "version": "0.7.1",
      "environment": {"os_release": Path("/etc/os-release").read_text(errors="replace")[:2048] if Path("/etc/os-release").exists() else None,
                      "architecture": os.uname().machine, "uid": uid, "memory_bytes": None},
      "runtime": {"docker": command_version("docker", ["--version"]),
                  "docker_compose": command_version("docker", ["compose", "version"]),
                  "nvidia_smi": command_version("nvidia-smi", ["--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]),
                  "vulkaninfo": command_version("vulkaninfo", ["--summary"]),
                  "qemu_img": command_version("qemu-img", ["--version"]),
                  "wine": command_version("wine", ["--version"])},
      "graphics": {"display_set": bool(os.environ.get("DISPLAY")), "wayland_display_set": bool(os.environ.get("WAYLAND_DISPLAY")),
                   "xauthority_readable": bool(os.environ.get("XAUTHORITY") and os.access(os.environ["XAUTHORITY"], os.R_OK)),
                   "x11_socket_present": Path("/tmp/.X11-unix").is_dir()},
      "audio": {"pulse_socket_present": (runtime_dir / "pulse/native").is_socket(),
                "pipewire_socket_present": (runtime_dir / "pipewire-0").is_socket(),
                "pulse_server_set": bool(os.environ.get("PULSE_SERVER"))},
      "input": {"input_directory_present": dev_input.is_dir(),
                "candidate_device_count": sum(1 for p in dev_input.glob("event*") if p.is_char_device()) if dev_input.is_dir() else 0,
                "mapped_by_default": False},
      "policy": "Read-only diagnostics only. It does not request elevated permissions or change input/display permissions."
    }
    try:
        host["environment"]["memory_bytes"] = int(Path("/proc/meminfo").read_text().split("MemTotal:")[1].split()[0]) * 1024
    except Exception: pass
    raw = json.dumps(host, indent=2, ensure_ascii=False)
    print(raw)
    out = ROOT / "data" / "host-capabilities.json"
    if "--write" in sys.argv[1:]:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(raw + "\n", encoding="utf-8")
        print(f"\nReport written to {out}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
