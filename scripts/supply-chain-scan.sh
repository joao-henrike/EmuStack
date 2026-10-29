#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT="$(cd -- "$(dirname -- "\${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="$ROOT/supply-chain-tools.json"
ARTIFACT_DIR="\${EMUSTACK_SECURITY_ARTIFACTS_DIR:-$ROOT/artifacts}"
IMAGE_REF="\${EMUSTACK_SCAN_IMAGE:-$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["target_image"])' "$LOCK_FILE")}"

for required in curl sha256sum tar python3 docker; do
  command -v "$required" >/dev/null 2>&1 || {
    echo "ERROR: required command not found: $required" >&2
    exit 2
  }
done
[[ -f "$LOCK_FILE" ]] || { echo "ERROR: missing supply-chain lock: $LOCK_FILE" >&2; exit 2; }

mkdir -p "$ARTIFACT_DIR"
work_dir="$(mktemp -d "\${TMPDIR:-/tmp}/emustack-supply-chain.XXXXXX")"
trap 'rm -rf -- "$work_dir"' EXIT

read_tool_field() {
  python3 - "$LOCK_FILE" "$1" "$2" <<'PY'
import json
import sys
from pathlib import Path

lock_path, tool_id, field = sys.argv[1:]
data = json.loads(Path(lock_path).read_text(encoding="utf-8"))
matches = [tool for tool in data["tools"] if tool.get("id") == tool_id]
if len(matches) != 1:
    raise SystemExit(f"Expected exactly one locked tool {tool_id!r}")
value = matches[0].get(field)
if not isinstance(value, str) or not value:
    raise SystemExit(f"Missing locked field {tool_id}.{field}")
print(value)
PY
}

install_locked_tool() {
  local tool_id="$1"
  local tool_version url expected_sha executable archive tool_dir version_output
  tool_version="$(read_tool_field "$tool_id" version)"
  url="$(read_tool_field "$tool_id" url)"
  expected_sha="$(read_tool_field "$tool_id" sha256)"
  executable="$(read_tool_field "$tool_id" executable)"
  [[ "$expected_sha" =~ ^[0-9a-f]{64}$ ]] || {
    echo "ERROR: invalid SHA-256 in lock for $tool_id" >&2
    return 2
  }
  case "$tool_id:$url" in
    "syft:https://github.com/anchore/syft/releases/download/v$tool_version/"*) ;;
    "trivy:https://github.com/aquasecurity/trivy/releases/download/v$tool_version/"*) ;;
    *)
      echo "ERROR: unapproved or moving release URL for $tool_id: $url" >&2
      return 2
      ;;
  esac

  tool_dir="$work_dir/$tool_id"
  mkdir -p "$tool_dir"
  archive="$tool_dir/$tool_id.tar.gz"
  echo "Downloading pinned $tool_id $tool_version" >&2
  curl --fail --location --retry 3 --retry-all-errors --silent --show-error "$url" --output "$archive"
  printf '%s  %s\n' "$expected_sha" "$archive" | sha256sum --check >&2
  tar -xzf "$archive" -C "$tool_dir"
  [[ -x "$tool_dir/$executable" ]] || {
    echo "ERROR: expected executable missing after verified extraction: $tool_id/$executable" >&2
    return 2
  }
  if [[ "$tool_id" == "syft" ]]; then
    version_output="$("$tool_dir/$executable" version 2>&1)"
  else
    version_output="$("$tool_dir/$executable" --version 2>&1)"
  fi
  grep -F -- "$tool_version" <<<"$version_output" >/dev/null || {
    echo "ERROR: version output does not match locked $tool_id $tool_version" >&2
    printf '%s\n' "$version_output" >&2
    return 2
  }
  printf '%s\n' "$version_output" > "$ARTIFACT_DIR/$tool_id-version.txt"
  printf '%s\n' "$tool_dir/$executable"
}

SYFT_BIN="$(install_locked_tool syft)"
TRIVY_BIN="$(install_locked_tool trivy)"

docker image inspect "$IMAGE_REF" >/dev/null
IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE_REF")"
[[ "$IMAGE_ID" =~ ^sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: Docker returned an unexpected image ID: $IMAGE_ID" >&2
  exit 2
}

SBOM_PATH="$ARTIFACT_DIR/emustack-image.spdx.json"
TRIVY_PATH="$ARTIFACT_DIR/emustack-trivy-vulnerabilities.json"
SUMMARY_PATH="$ARTIFACT_DIR/supply-chain-summary.md"
TOOLS_PATH="$ARTIFACT_DIR/supply-chain-tool-lock.json"

cp "$LOCK_FILE" "$TOOLS_PATH"
echo "Generating SPDX JSON SBOM for $IMAGE_REF ($IMAGE_ID)"
"$SYFT_BIN" "docker:$IMAGE_REF" --output "spdx-json=$SBOM_PATH"

echo "Scanning OS/library vulnerabilities (HIGH,CRITICAL); findings are report-only per supply-chain-tools.json"
"$TRIVY_BIN" image \
  --image-src docker \
  --scanners vuln \
  --vuln-type os,library \
  --severity HIGH,CRITICAL \
  --exit-code 0 \
  --timeout 10m \
  --format json \
  --output "$TRIVY_PATH" \
  "$IMAGE_REF"

python3 - "$LOCK_FILE" "$SBOM_PATH" "$TRIVY_PATH" "$SUMMARY_PATH" "$IMAGE_REF" "$IMAGE_ID" <<'PY'
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

lock_path, sbom_path, trivy_path, summary_path, image_ref, image_id = sys.argv[1:]
lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
sbom = json.loads(Path(sbom_path).read_text(encoding="utf-8"))
scan = json.loads(Path(trivy_path).read_text(encoding="utf-8"))
packages = sbom.get("packages", [])
severity_counts = Counter()
findings = []
for result in scan.get("Results") or []:
    for vulnerability in result.get("Vulnerabilities") or []:
        severity = str(vulnerability.get("Severity") or "UNKNOWN").upper()
        severity_counts[severity] += 1
        findings.append({
            "severity": severity,
            "id": str(vulnerability.get("VulnerabilityID") or "UNKNOWN"),
            "package": str(vulnerability.get("PkgName") or "UNKNOWN"),
            "installed": str(vulnerability.get("InstalledVersion") or "unknown"),
            "fixed": str(vulnerability.get("FixedVersion") or "no fix listed"),
            "target": str(result.get("Target") or "unknown"),
        })
rank = {"CRITICAL": 0, "HIGH": 1}
findings.sort(key=lambda item: (rank.get(item["severity"], 9), item["package"], item["id"]))
created = datetime.now(timezone.utc).isoformat()
policy = lock.get("scan_policy") or {}
syft_version = next((tool["version"] for tool in lock["tools"] if tool["id"] == "syft"), "unknown")
trivy_version = next((tool["version"] for tool in lock["tools"] if tool["id"] == "trivy"), "unknown")
lines = [
    "# EmuStack supply-chain scan",
    "",
    f"- Generated UTC: {created}",
    f"- Image reference: {image_ref}",
    f"- Immutable local image ID: {image_id}",
    "- SBOM: emustack-image.spdx.json (SPDX JSON)",
    f"- SPDX packages/components recorded: {len(packages)}",
    f"- Syft version: {syft_version}",
    f"- Trivy version: {trivy_version}",
    "- Scan scope: OS and library vulnerabilities, severities HIGH and CRITICAL.",
    f"- Policy: {policy.get('mode', 'unspecified')}; findings do not fail CI while the baseline is being reviewed.",
    "- Blocking errors: download failures, checksum/version mismatches, missing SBOM, or scanner execution/JSON errors.",
    "- This report is a snapshot of the scanner database at run time; vulnerability intelligence can change between runs.",
    "",
    "## Finding counts",
    "",
    "| Severity | Count |",
    "|---|---:|",
]
for severity in ("CRITICAL", "HIGH", "UNKNOWN"):
    lines.append(f"| {severity} | {severity_counts.get(severity, 0)} |")
lines.extend(["", "## HIGH/CRITICAL findings (up to 100 shown)", ""])
if not findings:
    lines.append("No HIGH/CRITICAL findings were reported for the scanned image by this Trivy database snapshot.")
else:
    lines.extend([
        "| Severity | Vulnerability | Package | Installed | Fixed version | Target |",
        "|---|---|---|---|---|---|",
    ])
    for finding in findings[:100]:
        cells = [finding[key].replace("|", "\\|").replace("\n", " ") for key in ("severity", "id", "package", "installed", "fixed", "target")]
        lines.append("| " + " | ".join(cells) + " |")
if len(findings) > 100:
    lines.extend(["", f"Showing 100 of {len(findings)} findings; see the complete JSON artifact."])
lines.extend([
    "",
    "## Triage policy",
    "",
    "Do not silently suppress unfixed findings. For each HIGH/CRITICAL result, review package reachability, upstream fix status, and whether the vulnerable code is present in the shipped image. Before making findings blocking, establish a reviewed baseline, document false-positive/accepted-risk exceptions with expiry dates, and keep scanner/tool integrity failures blocking.",
    "",
])
Path(summary_path).write_text("\n".join(lines), encoding="utf-8")
print(
    f"Supply-chain scan complete: {len(packages)} SBOM packages; "
    f"{severity_counts.get('CRITICAL', 0)} CRITICAL and {severity_counts.get('HIGH', 0)} HIGH finding(s)."
)
PY

test -s "$SBOM_PATH"
test -s "$TRIVY_PATH"
test -s "$SUMMARY_PATH"
echo "Supply-chain artifacts: $SBOM_PATH $TRIVY_PATH $SUMMARY_PATH"
