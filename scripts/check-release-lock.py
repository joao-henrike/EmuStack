#!/usr/bin/env python3
"""Validate release-lock.json and clearly report what is and is not reproducible."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PINNED_MODES = {"pinned", "pinned-url"}
ALLOWED_PINNED_URL_HOSTS = {"stable.eden-emu.dev", "dl.dolphin-emu.org"}
SHA = re.compile(r"^[0-9a-f]{64}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

def validate(path: Path, require_strict: bool = False, require_pins: bool = False) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Invalid release lock schema_version")
    if not isinstance(data.get("strict"), bool) or not isinstance(data.get("items"), dict):
        raise ValueError("release lock needs boolean strict and object items")
    if require_strict and not data["strict"]:
        raise ValueError("strict=true required; run the first successful online build and export a lock")
    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    catalog_ids = {entry["id"] for entry in catalog.get("emulators", [])}
    items = data["items"]
    if data["strict"] and set(items) != catalog_ids:
        raise ValueError(f"Strict lock coverage mismatch: missing={sorted(catalog_ids-set(items))}, extra={sorted(set(items)-catalog_ids)}")
    pinned = skipped = 0
    for ident, item in items.items():
        if not isinstance(item, dict): raise ValueError(f"{ident}: lock item must be an object")
        mode = item.get("mode")
        if mode == "pinned":
            if not REPO.fullmatch(str(item.get("repo", ""))): raise ValueError(f"{ident}: invalid pinned repo")
            if not str(item.get("tag", "")).strip() or not str(item.get("asset", "")).strip(): raise ValueError(f"{ident}: missing pinned tag/asset")
            if not SHA.fullmatch(str(item.get("sha256", "")).lower()): raise ValueError(f"{ident}: invalid SHA-256")
            pinned += 1
        elif mode == "pinned-url":
            url = urlparse(str(item.get("url", "")))
            if url.scheme != "https" or url.hostname not in ALLOWED_PINNED_URL_HOSTS: raise ValueError(f"{ident}: pinned URL host is not allowlisted")
            if not SHA.fullmatch(str(item.get("sha256", "")).lower()): raise ValueError(f"{ident}: invalid SHA-256")
            pinned += 1
        elif mode == "skip-upstream":
            if not str(item.get("reason", "")).strip(): raise ValueError(f"{ident}: skip-upstream needs a reason")
            skipped += 1
        else:
            raise ValueError(f"{ident}: unsupported lock mode {mode!r}")
    if require_pins and pinned == 0:
        raise ValueError("No verified upstream asset was pinnable; do not freeze an empty strict lock")
    return pinned, skipped

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", nargs="?", type=Path, default=ROOT / "release-lock.json")
    parser.add_argument("--require-strict", action="store_true")
    parser.add_argument("--require-pins", action="store_true")
    args = parser.parse_args()
    try:
        pinned, skipped = validate(args.lock, args.require_strict, args.require_pins)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"LOCK FAIL: {exc}", file=sys.stderr); return 1
    print(f"LOCK OK: {pinned} hashed upstream asset(s) pinned; {skipped} entry/entries explicitly skipped with reasons.")
    if args.require_strict:
        print("Scope limitation: the Debian base-image digest is pinned; Debian APT is time-pinned only when APT_SNAPSHOT_TIMESTAMP is set. This is not a bit-for-bit reproducibility guarantee.")
    return 0
if __name__ == "__main__": raise SystemExit(main())
