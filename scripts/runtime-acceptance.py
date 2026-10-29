#!/usr/bin/env python3
"""Runtime acceptance: Docker topology plus optional host GUI/audio/GPU/input probes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from runtime_probes import env_flag, has_readonly_device_mapping, is_allowed_input_device, is_software_vulkan_renderer, parse_env_file

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8765"
DASHBOARD_CONTAINER_ID: str | None = None
HOST_API_REACHABLE: bool | None = None


def run(args: list[str], check: bool = True, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    try:
        p = subprocess.run(
            args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Command timed out after {timeout}s: {' '.join(args)}") from exc
    if check and p.returncode:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(args)}\n{p.stderr.strip()[:1200]}")
    return p


def api(path: str, method: str = "GET", payload: dict | None = None):
    """Probe the published host port; fall back to dashboard loopback if the runner isolates it."""
    global HOST_API_REACHABLE
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json", "Origin": "http://127.0.0.1:8765", "X-EmuStack-Request": "1"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            HOST_API_REACHABLE = True
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
        except Exception:
            body = {}
        HOST_API_REACHABLE = True
        return exc.code, body
    except urllib.error.URLError:
        HOST_API_REACHABLE = False
        if not DASHBOARD_CONTAINER_ID:
            raise RuntimeError("Dashboard container ID is not available for internal API fallback")
        script = "\n".join([
            "import json,sys,urllib.request,urllib.error",
            "path,method,payload=sys.argv[1:4]",
            "obj=json.loads(payload) if payload else None",
            "data=json.dumps(obj).encode() if obj is not None else None",
            "req=urllib.request.Request('http://127.0.0.1:8765'+path,data=data,method=method,headers={'Content-Type':'application/json','Host':'127.0.0.1:8765','Origin':'http://127.0.0.1:8765','X-EmuStack-Request':'1'})",
            "try:",
            " with urllib.request.urlopen(req,timeout=5) as resp: result={'status':resp.status,'body':json.loads(resp.read().decode())}",
            "except urllib.error.HTTPError as exc:",
            " try: body=json.loads(exc.read().decode())",
            " except Exception: body={}",
            " result={'status':exc.code,'body':body}",
            "print(json.dumps(result))",
        ])
        result = run([
            "docker", "exec", DASHBOARD_CONTAINER_ID, "python3", "-c", script,
            path, method, json.dumps(payload) if payload is not None else "",
        ], check=False, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(f"Dashboard internal API probe failed for {path}: {result.stderr.strip()[:800]}")
        response = json.loads(result.stdout)
        return int(response["status"]), response.get("body", {})


def compose(*args: str):
    cmd = ["docker", "compose", "-f", "compose.yaml"]
    if Path(ROOT / "compose.override.yaml").is_file():
        cmd += ["-f", "compose.override.yaml"]
    if os.environ.get("USE_NVIDIA") == "1":
        cmd += ["-f", "compose.nvidia.yaml"]
    return run(cmd + list(args))


def container_env(container: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in container.get("Config", {}).get("Env", []) or []:
        if "=" in entry:
            key, value = entry.split("=", 1)
            result[key] = value
    return result


def dashboard_health_load_smoke() -> dict[str, int | float]:
    """Send a fixed, read-only burst to dashboard loopback from its own container."""
    if not DASHBOARD_CONTAINER_ID:
        raise RuntimeError("Dashboard container ID is not available for bounded API smoke")
    probe_script = r"""
import concurrent.futures
import json
import math
import time
import urllib.request

REQUESTS = 25
WORKERS = 4
URL = "http://127.0.0.1:8765/api/health"

def one(_index):
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(URL, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
            ok = response.status == 200 and payload.get("healthy") is True and "environments" not in payload
            error = None if ok else "unexpected-health-response"
    except Exception as exc:
        ok = False
        error = type(exc).__name__
    return {"ok": ok, "ms": (time.perf_counter() - started) * 1000, "error": error}

with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
    results = list(pool.map(one, range(REQUESTS)))
latencies = sorted(item["ms"] for item in results)
p95_index = min(len(latencies) - 1, math.ceil(0.95 * len(latencies)) - 1)
report = {
    "requests": len(results),
    "concurrency": WORKERS,
    "failures": sum(1 for item in results if not item["ok"]),
    "p50_ms": round(latencies[len(latencies) // 2], 2),
    "p95_ms": round(latencies[p95_index], 2),
    "max_ms": round(latencies[-1], 2),
    "failure_kinds": sorted({item["error"] for item in results if item["error"]}),
}
print(json.dumps(report, sort_keys=True))
raise SystemExit(0 if report["requests"] == REQUESTS and report["failures"] == 0 else 1)
"""
    result = run(
        ["docker", "exec", DASHBOARD_CONTAINER_ID, "python3", "-c", probe_script],
        check=False,
        timeout=20,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Bounded dashboard health API smoke failed: "
            f"{result.stdout.strip()[:800]} {result.stderr.strip()[:800]}"
        )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Bounded dashboard health API smoke did not return JSON") from exc
    if report.get("requests") != 25 or report.get("concurrency") != 4 or report.get("failures") != 0:
        raise RuntimeError(f"Bounded dashboard health API smoke returned unexpected results: {report}")
    return report


def probe_record(probes: list[dict], warnings: list[str], errors: list[str], name: str,
                 ok: bool, detail: str, configured: bool, required: bool) -> None:
    if ok:
        status = "PASS"
    elif required:
        status = "FAIL"
        errors.append(f"{name}: {detail}")
    elif configured:
        status = "WARN"
        warnings.append(f"{name}: {detail}")
    else:
        status = "INFO"
    probes.append({"name": name, "status": status, "detail": detail[:300]})


def runtime_hardware_probes(env_containers: dict[str, dict], profiles: list[dict]) -> tuple[list[dict], list[str], list[str]]:
    """Probe shared desktop integrations without reading controller events or launching games."""
    probes: list[dict] = []
    warnings: list[str] = []
    errors: list[str] = []
    require_gui = env_flag("EMUSTACK_REQUIRE_GUI")
    require_audio = env_flag("EMUSTACK_REQUIRE_AUDIO")
    require_vulkan = env_flag("EMUSTACK_REQUIRE_VULKAN")
    require_gpu = env_flag("EMUSTACK_REQUIRE_GPU")
    require_input = env_flag("EMUSTACK_REQUIRE_INPUT")

    # GUI tests touch only the X server metadata; no window or game is launched.
    display_configured = any(container_env(c).get("DISPLAY") for c in env_containers.values())
    gui_failures: list[str] = []
    if display_configured:
        for env_id, container in env_containers.items():
            env = container_env(container)
            mounts = container.get("Mounts", []) or []
            has_socket = any(m.get("Destination") == "/tmp/.X11-unix" for m in mounts)
            has_xauth = any(m.get("Destination") == "/tmp/.Xauthority" for m in mounts)
            display = env.get("DISPLAY", "")
            if not display or not has_socket or not has_xauth:
                gui_failures.append(env_id)
                continue
            result = run(["docker", "exec", container["Id"], "xdpyinfo", "-display", display], check=False, timeout=12)
            if result.returncode != 0:
                gui_failures.append(env_id)
        gui_ok = not gui_failures
        detail = "X11/XWayland server reachable from all 20 agents" if gui_ok else "X11 probe failed for: " + ", ".join(gui_failures)
        probe_record(probes, warnings, errors, "display/X11", gui_ok, detail, True, require_gui)
    else:
        probe_record(probes, warnings, errors, "display/X11", False, "GUI override has no DISPLAY; run host-setup.sh from an X11/XWayland desktop session", False, require_gui)

    # Audio is tested from one representative agent; a configured socket is not enough by itself.
    representative_id = os.environ.get("EMUSTACK_PROBE_ENV", "rpcs3").strip()
    valid_ids = {str(p.get("id")) for p in profiles}
    if representative_id not in valid_ids:
        representative_id = "rpcs3"
    representative = env_containers[representative_id]
    representative_env = container_env(representative)
    pulse_configured = bool(representative_env.get("PULSE_SERVER")) and any(
        m.get("Destination") == "/tmp/pulse/native" for m in representative.get("Mounts", []) or []
    )
    if pulse_configured:
        audio = run(["docker", "exec", representative["Id"], "pactl", "info"], check=False, timeout=12)
        audio_ok = audio.returncode == 0 and "Server Name:" in audio.stdout
        audio_detail = "PulseAudio/PipeWire Pulse-protocol socket is reachable" if audio_ok else "pactl could not connect to configured Pulse socket"
        probe_record(probes, warnings, errors, "audio", audio_ok, audio_detail, True, require_audio)
    else:
        probe_record(probes, warnings, errors, "audio", False, "Pulse-protocol socket is not configured; rerun host-setup.sh from a desktop session with audio", False, require_audio)

    # Vulkan and the actual renderer are checked separately: a software Vulkan driver is not GPU acceleration.
    vulkan = run(["docker", "exec", representative["Id"], "vulkaninfo", "--summary"], check=False, timeout=20)
    vulkan_ok = vulkan.returncode == 0 and ("GPU0" in vulkan.stdout or "deviceName" in vulkan.stdout)
    vk_output = vulkan.stdout + "\n" + vulkan.stderr
    software_vk = is_software_vulkan_renderer(vk_output)
    device_lines = [line.strip() for line in vulkan.stdout.splitlines() if "deviceName" in line or "GPU0" in line]
    vk_detail = ("; ".join(device_lines[:3]) if device_lines else "vulkaninfo did not enumerate a device")
    if software_vk:
        vk_detail += "; software renderer detected"
    probe_record(probes, warnings, errors, "Vulkan", vulkan_ok, vk_detail, True, require_vulkan or require_gpu)
    gpu_ok = vulkan_ok and not software_vk
    gpu_detail = vk_detail if gpu_ok else ("Vulkan reports only a software renderer" if vulkan_ok and software_vk else "hardware Vulkan renderer not confirmed")
    probe_record(probes, warnings, errors, "GPU acceleration", gpu_ok, gpu_detail, True, require_gpu)

    # The agent should see only the one explicitly mapped device. This does not consume events or prove button mapping.
    host_env = parse_env_file(ROOT / ".env")
    input_path = host_env.get("EMUSTACK_INPUT_DEVICE", "")
    input_env = host_env.get("EMUSTACK_INPUT_ENV", "")
    if input_path and not is_allowed_input_device(input_path):
        probe_record(probes, warnings, errors, "controller device mapping", False, "configured input path is outside the allowed /dev/input/eventN or /dev/input/jsN form", True, require_input)
    elif input_path and input_env in env_containers:
        container = env_containers[input_env]
        mapped = has_readonly_device_mapping(container.get("HostConfig", {}) or {}, input_path)
        readable = False
        if mapped:
            result = run(["docker", "exec", container["Id"], "test", "-r", input_path], check=False, timeout=8)
            readable = result.returncode == 0
        input_ok = mapped and readable
        detail = f"{input_path} is mapped read-only to env-{input_env}" if input_ok else f"configured device {input_path} is not mapped read-only and readable in env-{input_env}"
        probe_record(probes, warnings, errors, "controller device mapping", input_ok, detail, True, require_input)
    else:
        probe_record(probes, warnings, errors, "controller device mapping", False, "no explicit EMUSTACK_INPUT_DEVICE/EMUSTACK_INPUT_ENV mapping; no input device is passed by default", False, require_input)

    return probes, warnings, errors


def write_report(checks: list[str], probes: list[dict], warnings: list[str], errors: list[str]) -> Path:
    data_dir = ROOT / "data"
    if data_dir.is_symlink():
        raise RuntimeError("Refusing to write acceptance report through a symlinked data directory")
    data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = data_dir / "runtime-acceptance.json"
    payload = {
        "schema_version": 1,
        "project": "EmuStack",
        "version": "0.7.1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL" if errors else "PASS",
        "structural_checks": checks,
        "probes": probes,
        "warnings": warnings,
        "errors": errors,
        "limitations": [
            "Does not guarantee compatibility of any specific game.",
            "Does not prove the original firmware/dashboard actually booted.",
            "Controller probe checks mapping/read access only; it does not capture or validate inputs.",
        ],
    }
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)
    return target


def main() -> int:
    if not shutil_which("docker"):
        print("FAIL: docker CLI not found; this test must run on the target host.", file=sys.stderr)
        return 2
    checks: list[str] = []
    compose("config", "--quiet")
    checks.append("Compose configuration valid")
    payload = json.loads((ROOT / "environments.json").read_text())
    profiles = payload["environments"]
    if len(profiles) != 20:
        raise RuntimeError(f"Expected 20 environments, found {len(profiles)}")
    env_ids = [p["id"] for p in profiles]
    source_seen = {k: set() for k in ("games", "bios", "saves", "home", "emulators")}
    env_containers: dict[str, dict] = {}
    network_ids: set[str] = set()
    for env_id in env_ids:
        ids = compose("ps", "-q", f"env-{env_id}").stdout.split()
        if len(ids) != 1:
            raise RuntimeError(f"env-{env_id}: expected one running container; got {len(ids)}. Start stack with build-and-audit.sh first.")
        deadline = time.monotonic() + 60
        container = None
        while time.monotonic() < deadline:
            candidate = json.loads(run(["docker", "inspect", ids[0]]).stdout)[0]
            health = candidate.get("State", {}).get("Health", {}).get("Status")
            if candidate.get("State", {}).get("Status") == "running" and health == "healthy":
                container = candidate
                break
            time.sleep(2)
        if container is None:
            raise RuntimeError(f"env-{env_id} did not become healthy within 60 seconds; inspect docker compose logs env-{env_id}")
        service = container.get("Config", {}).get("Labels", {}).get("com.docker.compose.service")
        if service != f"env-{env_id}":
            raise RuntimeError(f"Unexpected container label for {env_id}: {service}")
        state = container.get("State", {})
        if state.get("Status") != "running":
            raise RuntimeError(f"env-{env_id} not running ({state.get('Status')})")
        health = state.get("Health", {}).get("Status")
        if health != "healthy":
            raise RuntimeError(f"env-{env_id} health is {health!r}; inspect logs")
        host_config = container.get("HostConfig", {})
        if not host_config.get("ReadonlyRootfs"):
            raise RuntimeError(f"env-{env_id} root filesystem is not read-only")
        if "ALL" not in [x.upper() for x in host_config.get("CapDrop", [])]:
            raise RuntimeError(f"env-{env_id} did not drop all Linux capabilities")
        if not any("no-new-privileges:true" in x for x in host_config.get("SecurityOpt", []) or []):
            raise RuntimeError(f"env-{env_id} lacks no-new-privileges")
        mounts = container.get("Mounts", [])
        if any(m.get("Destination") == "/var/run/docker.sock" for m in mounts):
            raise RuntimeError(f"env-{env_id} has Docker socket mounted")
        for key in source_seen:
            target = {"games": "/games", "bios": "/bios", "saves": "/saves", "home": "/home/emu", "emulators": "/custom-emulators"}[key]
            rows = [m for m in mounts if m.get("Destination") == target]
            if len(rows) != 1:
                raise RuntimeError(f"env-{env_id} missing/duplicate mount {target}")
            src = rows[0].get("Source", "")
            expected_source = ROOT / "data" / "environments" / env_id / key
            if not src.endswith(f"/data/environments/{env_id}/{key}"):
                raise RuntimeError(f"env-{env_id} mount {target} points outside its own root: {src}")
            if Path(src).is_symlink() or Path(src).resolve() != expected_source.resolve():
                raise RuntimeError(f"env-{env_id} mount {target} resolves through a symlink or unexpected path: {src}")
            if src in source_seen[key]:
                raise RuntimeError(f"{key} directory shared by two environments: {src}")
            source_seen[key].add(src)
        networks = container.get("NetworkSettings", {}).get("Networks", {})
        if len(networks) != 1:
            raise RuntimeError(f"env-{env_id} participates in {len(networks)} networks instead of exactly one")
        nname = next(iter(networks))
        net = json.loads(run(["docker", "network", "inspect", nname]).stdout)[0]
        if not net.get("Internal"):
            raise RuntimeError(f"Network {nname} is not internal")
        expected_network = f"env-{env_id}-net"
        actual_network = net.get("Labels", {}).get("com.docker.compose.network")
        if actual_network != expected_network:
            raise RuntimeError(f"env-{env_id} is attached to unexpected network {actual_network!r}")
        expected_index = env_ids.index(env_id) + 1
        ipam_config = (net.get("IPAM", {}).get("Config") or [{}])[0]
        if ipam_config.get("Subnet") != f"172.28.{expected_index}.0/24" or ipam_config.get("Gateway") != f"172.28.{expected_index}.1":
            raise RuntimeError(f"Network {nname} has unexpected IPAM configuration: {ipam_config}")
        endpoint = container.get("NetworkSettings", {}).get("Networks", {}).get(nname, {})
        if endpoint.get("IPAddress") != f"172.28.{expected_index}.2":
            raise RuntimeError(f"env-{env_id} does not have reserved agent IP .2: {endpoint.get('IPAddress')}")
        network_id = net.get("Id")
        if not network_id or network_id in network_ids:
            raise RuntimeError(f"Network is shared/reused by multiple environments: {nname}")
        network_ids.add(network_id)
        env_containers[env_id] = container
    checks += ["20 agents healthy", "every environment has unique mounts", "each agent has a unique internal network", "runtime hardening flags verified"]

    dashboard_ids = compose("ps", "-q", "dashboard").stdout.split()
    if len(dashboard_ids) != 1:
        raise RuntimeError("Dashboard container is not running")
    global DASHBOARD_CONTAINER_ID
    DASHBOARD_CONTAINER_ID = dashboard_ids[0]
    dashboard = json.loads(run(["docker", "inspect", dashboard_ids[0]]).stdout)[0]
    published = dashboard.get("HostConfig", {}).get("PortBindings", {}).get("8765/tcp") or []
    if len(published) != 1 or published[0].get("HostIp") != "127.0.0.1" or published[0].get("HostPort") != "8765":
        raise RuntimeError(f"Dashboard port must be published only on 127.0.0.1:8765; got {published}")
    checks.append("dashboard port published only on host loopback 127.0.0.1:8765")
    dmounts = dashboard.get("Mounts", [])
    if any("/var/run/docker.sock" in m.get("Destination", "") or "/data/environments" in m.get("Source", "") for m in dmounts):
        raise RuntimeError("Dashboard mounts Docker socket or environment data")
    dnetworks = dashboard.get("NetworkSettings", {}).get("Networks", {})
    if len(dnetworks) != len(profiles):
        raise RuntimeError(f"Dashboard network count {len(dnetworks)}, expected {len(profiles)}")
    dashboard_network_ids = {value.get("NetworkID") for value in dnetworks.values()}
    if dashboard_network_ids != network_ids:
        raise RuntimeError("Dashboard does not join exactly the set of unique per-agent networks")
    checks.append("dashboard has orchestrator-only mounts and all agent networks")
    for index, env_id in enumerate(env_ids, 1):
        endpoint = next((entry for entry in dnetworks.values() if entry.get("IPAddress") == f"172.28.{index}.3"), None)
        if endpoint is None:
            raise RuntimeError(f"Dashboard does not have reserved IP 172.28.{index}.3 for {env_id}")
    trusted_env = next((entry for entry in dashboard.get("Config", {}).get("Env", []) if entry.startswith("EMUSTACK_CONTROL_TRUSTED_CLIENT_IPS=")), None)
    expected_gateways = {f"172.28.{index}.1" for index in range(1, len(env_ids) + 1)}
    actual_gateways = set(trusted_env.split("=", 1)[1].split(",")) if trusted_env else set()
    if actual_gateways != expected_gateways:
        raise RuntimeError("Dashboard trusted-client IP allowlist does not exactly match isolated-network gateways")
    checks.append("dashboard uses gateway IP allowlist; agent addresses are not trusted")

    # Emulate a compromised agent forging every HTTP header currently used by the UI.
    # The TCP source address must still be rejected before any state-changing route runs.
    spoof_probe = "\n".join([
        "import urllib.error, urllib.request",
        "req=urllib.request.Request('http://dashboard:8765/api/processes/stop',data=b'{}',method='POST',headers={'Host':'127.0.0.1:8765','X-EmuStack-Request':'1','Content-Type':'application/json'})",
        "try:",
        " urllib.request.urlopen(req,timeout=3)",
        " raise SystemExit('FAIL: spoofed state-changing request was accepted')",
        "except urllib.error.HTTPError as exc:",
        " print('HTTP',exc.code)",
        " raise SystemExit(0 if exc.code == 403 else 1)",
    ])
    metadata_probe = "\n".join([
        "import urllib.error, urllib.request",
        "req=urllib.request.Request('http://dashboard:8765/api/environments')",
        "try:",
        " urllib.request.urlopen(req,timeout=3)",
        " raise SystemExit('FAIL: agent read dashboard metadata')",
        "except urllib.error.HTTPError as exc:",
        " print('HTTP',exc.code)",
        " raise SystemExit(0 if exc.code == 403 else 1)",
    ])
    health_probe = "import json,urllib.request; data=json.load(urllib.request.urlopen('http://dashboard:8765/api/health',timeout=3)); print(data); raise SystemExit(0 if data.get('healthy') is True and 'environments' not in data else 1)"
    for env_id, container in env_containers.items():
        for name, probe in (("spoofed POST", spoof_probe), ("metadata GET", metadata_probe), ("minimal health", health_probe)):
            result = run(["docker", "exec", container["Id"], "python3", "-c", probe], check=False, timeout=8)
            expected_ok = result.returncode == 0 and (name == "minimal health" or "HTTP 403" in result.stdout)
            if not expected_ok:
                raise RuntimeError(f"env-{env_id} {name} boundary probe failed: {result.stdout} {result.stderr}")
    checks.append("20/20 agents denied spoofed POST and dashboard metadata GET; health response is minimal")

    for path in ("/api/health", "/api/environments", "/api/console-systems"):
        status, data = api(path)
        if status != 200:
            raise RuntimeError(f"{path} returned HTTP {status}")
        if not isinstance(data, dict):
            raise RuntimeError(f"{path} did not return a JSON object")
        if path == "/api/environments" and len(data.get("environments", [])) != 20:
            raise RuntimeError("API did not enumerate 20 environments")
        if path == "/api/console-systems" and not data.get("systems"):
            raise RuntimeError("Console-system capability matrix is empty")
    checks.append("dashboard health and capability APIs respond")

    # Bounded read-only concurrency probe; no launch/stop/data-changing endpoint is called.
    load_stats = dashboard_health_load_smoke()
    checks.append(
        "bounded dashboard health smoke passed: "
        f"{load_stats['requests']} requests / {load_stats['concurrency']} workers, "
        f"p95 {load_stats['p95_ms']} ms, max {load_stats['max_ms']} ms"
    )

    status, _ = api("/api/console-systems/launch", "POST", {"system": "ps5-system", "action": "boot"})
    if status not in (409, 400):
        raise RuntimeError(f"Unsupported PS5 system boot was not blocked as expected (HTTP {status})")
    checks.append("unsupported PS5 system boot correctly blocked")

    probes, warnings, errors = runtime_hardware_probes(env_containers, profiles)
    if HOST_API_REACHABLE is False:
        warnings.append("Host loopback API was unreachable from this runner; API behavior was checked inside the dashboard container. Verify host UI access on the deployment machine with curl http://127.0.0.1:8765/api/health.")
    report_path = write_report(checks, probes, warnings, errors)
    print("EmuStack runtime acceptance: " + ("PASS" if not errors else "FAIL"))
    for item in checks:
        print(f"  PASS  {item}")
    for probe in probes:
        print(f"  {probe['status']:4}  {probe['name']}: {probe['detail']}")
    for warning in warnings:
        print(f"  WARN  {warning}")
    for error in errors:
        print(f"  FAIL  {error}")
    print(f"  REPORT {report_path.relative_to(ROOT)}")
    print("Limit: this does NOT prove compatibility of any specific game or successful firmware/dashboard boot. Run per-console tests with authorized files and inspect the actual emulator window/log.")
    return 1 if errors else 0


def shutil_which(name: str) -> str | None:
    import shutil
    return shutil.which(name)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
