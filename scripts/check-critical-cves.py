#!/usr/bin/env python3
"""Fail CI on newly introduced CRITICAL vulnerability IDs per Docker image.

The snapshot of already observed vulnerabilities is NOT an exception/waiver.
It remains an unresolved triage backlog, separately shown in every report.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

EXPECTED_IMAGES = {"common", "dolphin", "mupen64plus"}
VULN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,}$")


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _ids(value: object, context: str) -> set[str]:
    if not isinstance(value, list):
        raise ValueError(f"{context}: expected a list")
    if not all(isinstance(item, str) and VULN_ID.fullmatch(item) and item != "UNKNOWN" for item in value):
        raise ValueError(f"{context}: invalid vulnerability identifier")
    if len(value) != len(set(value)):
        raise ValueError(f"{context}: duplicate vulnerability identifiers")
    return set(value)


def evaluate(matrix: dict, baseline: dict) -> tuple[dict, str, bool]:
    """Validate both inputs fail-closed; return report, Markdown, and pass flag."""
    if baseline.get("schema_version") != 1 or matrix.get("schema_version") != 1:
        raise ValueError("Unsupported schema version")
    policy = baseline.get("policy")
    if not isinstance(policy, dict) or policy.get("new_critical") != "block" or policy.get("known_critical") != "unresolved":
        raise ValueError("Critical regression policy must block new IDs and keep existing IDs unresolved")
    snapshots = baseline.get("images")
    observed = matrix.get("images")
    if not isinstance(snapshots, dict) or set(snapshots) != EXPECTED_IMAGES:
        raise ValueError("Baseline must enumerate exactly the three expected runtime images")
    if not isinstance(observed, dict) or set(observed) != EXPECTED_IMAGES:
        raise ValueError("Matrix must enumerate exactly the three expected runtime images")

    known_union: set[str] = set()
    rows: dict[str, dict] = {}
    new_found = False
    for name in sorted(EXPECTED_IMAGES):
        spec = snapshots[name]
        scan = observed[name]
        if not isinstance(spec, dict) or not isinstance(scan, dict):
            raise ValueError(f"{name}: baseline/matrix entry must be an object")
        if spec.get("image") != scan.get("image"):
            raise ValueError(f"{name}: image tag mismatch (possible wrong artifact or version)")
        allowed = _ids(spec.get("critical_ids"), f"{name}.baseline.critical_ids")
        seen = _ids(scan.get("critical_cve_ids"), f"{name}.matrix.critical_cve_ids")
        unique = scan.get("unique_cves")
        if not isinstance(unique, dict) or type(unique.get("CRITICAL")) is not int or unique["CRITICAL"] != len(seen):
            raise ValueError(f"{name}: critical count does not match unique IDs")
        package_findings = scan.get("package_findings")
        if not isinstance(package_findings, dict) or type(package_findings.get("CRITICAL")) is not int or package_findings["CRITICAL"] < len(seen):
            raise ValueError(f"{name}: invalid package-level CRITICAL count")
        known_union |= allowed
        new_ids = sorted(seen - allowed)
        removed_ids = sorted(allowed - seen)
        new_found |= bool(new_ids)
        rows[name] = {
            "image": spec["image"],
            "existing_unresolved": sorted(seen & allowed),
            "new_critical": new_ids,
            "no_longer_detected": removed_ids,
        }

    tracked = baseline.get("tracked")
    if not isinstance(tracked, dict) or set(tracked) != known_union:
        raise ValueError("All baseline vulnerability IDs must be individually tracked")
    for vuln_id, item in tracked.items():
        if not VULN_ID.fullmatch(vuln_id) or not isinstance(item, dict) or item.get("review") != "pending":
            raise ValueError(f"Invalid/unreviewed tracker entry for {vuln_id}")
        if not isinstance(item.get("source"), str) or not item["source"].startswith("https://security-tracker.debian.org/tracker/"):
            raise ValueError(f"Missing official Debian tracker reference for {vuln_id}")

    report = {
        "schema_version": 1,
        "source_run": baseline.get("source_run"),
        "policy": "block-new-critical-per-image",
        "pass": not new_found,
        "images": rows,
    }
    lines = [
        "# EmuStack CRITICAL vulnerability regression gate", "",
        f"- Result: **{'PASS' if report['pass'] else 'BLOCKED: new CRITICAL IDs found'}**",
        "- Policy: block new CRITICAL vulnerability IDs for each image, even if previously seen in another image.",
        "- Existing CRITICAL vulnerabilities are **unresolved** and still require independent review, patching or mitigation.",
        "- This gate is NOT a release approval, vulnerability waiver or risk acceptance.", "",
        "| Image | Already known and unresolved | Newly found (blocking) | No longer detected |",
        "|---|---:|---:|---:|",
    ]
    for name, row in rows.items():
        lines.append(f"| {name} | {len(row['existing_unresolved'])} | {len(row['new_critical'])} | {len(row['no_longer_detected'])} |")
    for name, row in rows.items():
        lines.extend(["", f"## {name}", ""])
        lines.append("- Newly found: " + (", ".join(row["new_critical"]) or "none"))
        lines.append("- Unresolved: " + (", ".join(row["existing_unresolved"]) or "none"))
        lines.append("- No longer detected: " + (", ".join(row["no_longer_detected"]) or "none"))
    lines.extend(["", "Tracked Debian advisories are listed in security-critical-baseline.json.", ""])
    return report, "\n".join(lines), report["pass"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        report, summary, passed = evaluate(read_json(args.matrix), read_json(args.baseline))
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(summary, encoding="utf-8")
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"CRITICAL regression gate ERROR: {exc}", flush=True)
        return 2
    print(summary, flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
