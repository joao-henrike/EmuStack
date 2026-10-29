#!/usr/bin/env python3
"""Read-only audit of per-emulator save/data paths.

The report contains only path candidates, directory states and aggregate counts;
it never lists file names or file contents. No directories are created, and no
save files are moved, linked, renamed or executed. Use --output only when you
explicitly want to persist the resulting diagnostic JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

SAVE_MANIFEST = "save-paths.json"
ENV_MANIFEST = "environments.json"


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read valid JSON from {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _safe_relative(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Path must be a non-empty relative POSIX path")
    if "\x00" in value or "\\" in value:
        raise ValueError("Path contains a forbidden character")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Path must remain inside the environment data root")
    return path


def _inspect_directory(data_root: Path, relative: str) -> dict[str, Any]:
    """Inspect a path component-by-component and refuse to follow any symlink."""
    try:
        rel = _safe_relative(relative)
    except ValueError as exc:
        return {"state": "unsafe-path", "reason": str(exc), "file_count": 0, "total_bytes": 0, "symlink_count": 0}

    data_root = Path(data_root)
    for ancestor in (data_root, *data_root.parents):
        if ancestor.is_symlink():
            return {"state": "unsafe-symlink", "reason": "data root or one of its parents is a symlink", "file_count": 0, "total_bytes": 0, "symlink_count": 1}
    if not data_root.exists():
        return {"state": "missing", "file_count": 0, "total_bytes": 0, "symlink_count": 0}
    if not data_root.is_dir():
        return {"state": "not-directory", "reason": "data root is not a directory", "file_count": 0, "total_bytes": 0, "symlink_count": 0}

    current = data_root
    for part in rel.parts:
        if current.is_symlink():
            return {"state": "unsafe-symlink", "reason": "a parent path is a symlink", "file_count": 0, "total_bytes": 0, "symlink_count": 1}
        if not current.exists():
            return {"state": "missing", "file_count": 0, "total_bytes": 0, "symlink_count": 0}
        if not current.is_dir():
            return {"state": "not-directory", "reason": "a parent path is not a directory", "file_count": 0, "total_bytes": 0, "symlink_count": 0}
        current = current / part
        if current.is_symlink():
            return {"state": "unsafe-symlink", "reason": "path itself is a symlink", "file_count": 0, "total_bytes": 0, "symlink_count": 1}
        if not current.exists():
            return {"state": "missing", "file_count": 0, "total_bytes": 0, "symlink_count": 0}
    if not current.is_dir():
        return {"state": "not-directory", "reason": "expected a directory", "file_count": 0, "total_bytes": 0, "symlink_count": 0}

    file_count = 0
    total_bytes = 0
    symlink_count = 0
    unreadable_count = 0
    for directory, dirs, files in os.walk(current, topdown=True, followlinks=False):
        safe_dirs: list[str] = []
        for name in dirs:
            candidate = Path(directory) / name
            try:
                if candidate.is_symlink():
                    symlink_count += 1
                else:
                    safe_dirs.append(name)
            except OSError:
                unreadable_count += 1
        dirs[:] = safe_dirs
        for name in files:
            candidate = Path(directory) / name
            try:
                if candidate.is_symlink():
                    symlink_count += 1
                    continue
                if candidate.is_file():
                    stat = candidate.stat(follow_symlinks=False)
                    file_count += 1
                    total_bytes += stat.st_size
            except OSError:
                unreadable_count += 1

    return {
        "state": "observed-directory",
        "file_count": file_count,
        "total_bytes": total_bytes,
        "symlink_count": symlink_count,
        "unreadable_count": unreadable_count,
    }


def audit_save_layout(project_root: Path, data_root: Path | None = None) -> dict[str, Any]:
    project_root = Path(project_root)
    data_root = Path(data_root) if data_root is not None else project_root / "data" / "environments"
    environment_doc = _load_object(project_root / ENV_MANIFEST)
    save_doc = _load_object(project_root / SAVE_MANIFEST)
    if environment_doc.get("schema_version") != 1 or save_doc.get("schema_version") != 1:
        raise ValueError("Unsupported environments/save-paths manifest schema version")
    env_records = environment_doc.get("environments")
    save_records = save_doc.get("profiles")
    if not isinstance(env_records, list) or not isinstance(save_records, list):
        raise ValueError("Expected environments and save-path profiles lists")

    env_by_id: dict[str, dict[str, Any]] = {}
    for environment in env_records:
        if not isinstance(environment, dict) or not isinstance(environment.get("id"), str):
            raise ValueError("Malformed environment record")
        identifier = environment["id"]
        if identifier in env_by_id:
            raise ValueError(f"Duplicate environment ID: {identifier}")
        env_by_id[identifier] = environment

    save_by_id: dict[str, dict[str, Any]] = {}
    for profile in save_records:
        if not isinstance(profile, dict) or not isinstance(profile.get("id"), str):
            raise ValueError("Malformed save-path profile")
        identifier = profile["id"]
        if identifier in save_by_id:
            raise ValueError(f"Duplicate save-path profile ID: {identifier}")
        save_by_id[identifier] = profile
    if set(env_by_id) != set(save_by_id):
        raise ValueError(
            "save-path/environment ID mismatch: "
            f"without save profile={sorted(set(env_by_id) - set(save_by_id))}; "
            f"without environment={sorted(set(save_by_id) - set(env_by_id))}"
        )

    reports: list[dict[str, Any]] = []
    for identifier in sorted(env_by_id):
        environment = env_by_id[identifier]
        profile = save_by_id[identifier]
        directories = environment.get("directories")
        if not isinstance(directories, dict):
            raise ValueError(f"environments.json:{identifier}: directories must be an object")
        root_relative = _safe_relative(directories.get("root"))
        home_relative = _safe_relative(directories.get("config_home"))
        saves_relative = _safe_relative(directories.get("saves"))
        try:
            home_subpath = home_relative.relative_to(root_relative)
            saves_subpath = saves_relative.relative_to(root_relative)
        except ValueError as exc:
            raise ValueError(f"Environment {identifier} has paths outside its declared root") from exc
        if len(root_relative.parts) != 3 or root_relative.parts[:2] != ("data", "environments") or root_relative.parts[2] != identifier:
            raise ValueError(f"Environment {identifier} has unexpected root: {root_relative}")
        if home_subpath.as_posix() != "home" or saves_subpath.as_posix() != "saves":
            raise ValueError(f"Environment {identifier} must keep the standard home/saves directories")

        home_rel = (PurePosixPath(identifier) / home_subpath).as_posix()
        saves_rel = (PurePosixPath(identifier) / saves_subpath).as_posix()
        home_state = _inspect_directory(data_root, home_rel)
        saves_state = _inspect_directory(data_root, saves_rel)
        candidates: list[dict[str, Any]] = []
        paths = profile.get("home_paths")
        if not isinstance(paths, list):
            raise ValueError(f"save-paths.json:{identifier}: home_paths must be a list")
        for candidate in paths:
            if not isinstance(candidate, dict):
                raise ValueError(f"save-paths.json:{identifier}: each home path must be an object")
            path = _safe_relative(candidate.get("path"))
            kind = candidate.get("kind")
            if not isinstance(kind, str) or not kind.strip():
                raise ValueError(f"save-paths.json:{identifier}: home path kind is required")
            inspect_rel = (PurePosixPath(identifier) / home_subpath / path).as_posix()
            state = _inspect_directory(data_root, inspect_rel)
            candidates.append({
                "path_relative_to_home": path.as_posix(),
                "kind": kind,
                "purpose": str(candidate.get("purpose", "")),
                **state,
            })

        model = profile.get("storage_model", "manual")
        confidence = profile.get("confidence", "needs-runtime-validation")
        if model == "unsupported":
            status = "unsupported-profile"
        elif home_state["state"] in {"unsafe-symlink", "unsafe-path", "not-directory"} or saves_state["state"] in {"unsafe-symlink", "unsafe-path", "not-directory"} or any(path["state"] in {"unsafe-symlink", "unsafe-path", "not-directory"} for path in candidates):
            status = "unsafe-path-needs-review"
        elif model == "rom-adjacent-or-configured":
            status = "runtime-validation-required-read-only-games"
        elif confidence == "needs-runtime-validation" or model == "manual":
            status = "manual-runtime-validation-required"
        elif any(path["state"] == "observed-directory" for path in candidates):
            status = "candidate-directory-observed-not-proof-of-save-use"
        elif home_state["state"] == "observed-directory" or saves_state["state"] == "observed-directory":
            status = "environment-directories-observed"
        else:
            status = "environment-not-provisioned"

        reports.append({
            "profile_id": identifier,
            "status": status,
            "storage_model": model,
            "confidence": confidence,
            "home_directory": home_state,
            "separate_saves_directory": saves_state,
            "candidate_paths": candidates,
            "source_url": profile.get("source_url"),
            "notes": profile.get("notes", ""),
            "evidence_limit": "Directory presence and file counts do not prove that the emulator wrote or loaded save data.",
        })

    candidate_count = sum(len(profile["candidate_paths"]) for profile in reports)
    present_count = sum(
        1 for profile in reports for path in profile["candidate_paths"]
        if path["state"] == "observed-directory"
    )
    manual_count = sum(1 for profile in reports if "validation-required" in profile["status"] or profile["status"].startswith("runtime-validation"))
    unsafe_count = sum(
        1 for profile in reports
        if profile["status"] == "unsafe-path-needs-review"
    )
    return {
        "project": "EmuStack",
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read-only",
        "data_root_label": "data/environments (or explicit --data-root); no absolute host paths are emitted",
        "summary": {
            "profiles": len(reports),
            "candidate_paths": candidate_count,
            "candidate_directories_observed": present_count,
            "profiles_needing_runtime_validation": manual_count,
            "profiles_with_unsafe_paths": unsafe_count,
        },
        "profiles": reports,
        "limitations": [
            "The script never creates, moves, renames, links, deletes, or executes files.",
            "Paths in save-paths.json are documented candidates, not proof of actual runtime writes.",
            "EmuStack snapshots include both each environment's home and saves directories; paths under home are not automatically moved into saves.",
            "A successful directory audit does not prove a save can be loaded by the emulator or game.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--data-root", type=Path, help="override the per-environment data root (read-only)")
    parser.add_argument("--output", type=Path, help="explicitly write the JSON report to this path")
    parser.add_argument("--strict", action="store_true", help="return nonzero if unsafe/symlinked paths are found")
    args = parser.parse_args()
    try:
        report = audit_save_layout(args.root, args.data_root)
    except (OSError, ValueError) as exc:
        print(f"SAVE LAYOUT AUDIT FAILED: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    print(rendered, end="")
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        try:
            output.chmod(0o600)
        except OSError:
            pass
        print(f"Report written to {output}", file=sys.stderr)
    if args.strict and report["summary"]["profiles_with_unsafe_paths"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
