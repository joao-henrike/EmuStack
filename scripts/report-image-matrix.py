#!/usr/bin/env python3
"""Compare isolated SPDX/Trivy inventories without hiding any vulnerabilities."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

IMAGES = {
    "common": "local/emustack:0.7.1",
    "dolphin": "local/emustack-dolphin:0.7.1",
    "mupen64plus": "local/emustack-mupen64plus:0.7.1",
}
SEVERITIES = ("CRITICAL", "HIGH")
RANK = {"CRITICAL": 2, "HIGH": 1}


def load_report(root: Path, name: str, image: str) -> dict:
    directory = root / name
    paths = {
        "scan": directory / "emustack-trivy-vulnerabilities.json",
        "sbom": directory / "emustack-image.spdx.json",
        "summary": directory / "supply-chain-summary.md",
    }
    for item in paths.values():
        if not item.is_file() or not item.stat().st_size:
            raise ValueError(f"Missing mandatory scan artifact for {image}: {item}")
    scan = json.loads(paths["scan"].read_text(encoding="utf-8"))
    sbom = json.loads(paths["sbom"].read_text(encoding="utf-8"))
    if not isinstance(scan, dict) or not isinstance(scan.get("Results"), list):
        raise ValueError(f"Invalid Trivy report for {image}")
    if not isinstance(sbom, dict) or not isinstance(sbom.get("packages"), list):
        raise ValueError(f"Invalid SPDX inventory for {image}")
    package_findings = Counter()
    severity_by_cve: dict[str, str] = {}
    for result in scan["Results"]:
        if not isinstance(result, dict):
            raise ValueError(f"Invalid Trivy result for {image}")
        for vulnerability in result.get("Vulnerabilities") or []:
            severity = str(vulnerability.get("Severity") or "").upper()
            if severity not in SEVERITIES:
                continue
            cve_id = str(vulnerability.get("VulnerabilityID") or "UNKNOWN")
            package_findings[severity] += 1
            if RANK[severity] > RANK.get(severity_by_cve.get(cve_id, ""), 0):
                severity_by_cve[cve_id] = severity
    unique = Counter(severity_by_cve.values())
    return {
        "image": image,
        "spdx_packages": len(sbom["packages"]),
        "package_findings": {severity: package_findings[severity] for severity in SEVERITIES},
        "unique_cves": {severity: unique[severity] for severity in SEVERITIES},
        "cve_ids": sorted(severity_by_cve),
        "critical_cve_ids": sorted(cve for cve, severity in severity_by_cve.items() if severity == "CRITICAL"),
        "_severities": severity_by_cve,
    }


def build_matrix(root: Path) -> tuple[dict, str]:
    images = {key: load_report(root, key, ref) for key, ref in IMAGES.items()}
    baseline = set(images["common"]["cve_ids"])
    extras = {
        name: sorted(set(images[name]["cve_ids"]) - baseline)
        for name in ("dolphin", "mupen64plus")
    }
    matrix = {
        "schema_version": 1,
        "baseline": "common",
        "images": {name: {key: value for key, value in stats.items() if not key.startswith("_")}
                   for name, stats in images.items()},
        "additional_cve_ids_vs_common": extras,
    }
    lines = [
        "# EmuStack image-specific vulnerability matrix",
        "",
        "Each runtime image was scanned separately. Counts are observations from Trivy,",
        "**not proof of exploitability**. The CI policy remains report-only for vulnerabilities.",
        "",
        "| Image | SPDX packages | CRITICAL package findings | HIGH package findings | Unique CRITICAL IDs | Unique HIGH IDs |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, stats in images.items():
        lines.append(
            f"| {name} | {stats['spdx_packages']} | "
            f"{stats['package_findings']['CRITICAL']} | {stats['package_findings']['HIGH']} | "
            f"{stats['unique_cves']['CRITICAL']} | {stats['unique_cves']['HIGH']} |"
        )
    lines.extend(["", "## New CVE IDs compared with common runtime", ""])
    for name in ("dolphin", "mupen64plus"):
        additional = extras[name]
        critical = [cve for cve in additional if images[name]["_severities"][cve] == "CRITICAL"]
        lines.extend([
            f"### {name}",
            "",
            f"- Additional unique vulnerability IDs: {len(additional)}",
            f"- Additional CRITICAL IDs: {', '.join(critical) if critical else 'none detected'}",
            f"- Full additional IDs: {', '.join(additional) if additional else 'none detected'}",
            "",
        ])
    lines.extend([
        "## Audit notes",
        "",
        "- Per-image subdirectories include complete SPDX JSON, Trivy JSON and scan summary.",
        "- A CVE absent from the common image may remain present in Dolphin or Mupen64Plus.",
        "- Never use an image split to justify suppressing unresolved vulnerabilities.",
        "- GPU, graphics, audio, controllers, firmware and gameplay require host-specific checks.",
        "",
    ])
    return matrix, "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", required=True, type=Path)
    args = parser.parse_args()
    root = args.artifacts_dir.resolve()
    matrix, summary = build_matrix(root)
    (root / "matrix.json").write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (root / "matrix-summary.md").write_text(summary, encoding="utf-8")
    for name, stats in matrix["images"].items():
        print(f"{name}: {stats['package_findings']['CRITICAL']} CRITICAL / "
              f"{stats['package_findings']['HIGH']} HIGH findings; "
              f"{len(stats['cve_ids'])} distinct IDs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
