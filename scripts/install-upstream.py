#!/usr/bin/env python3
"""Download only official, public emulator release assets during Docker build.

Downloads are source-whitelisted; GitHub assets are checksum-verified when the
maintainer publishes a SHA256SUMS/checksum file. Missing assets are recorded,
not replaced with guessed URLs or counterfeit launchers.
"""
from __future__ import annotations
import argparse
import hashlib
import html.parser
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

UA = "EmuStack-official-upstream-installer/0.7.1"
GITHUB_API = "https://api.github.com"

# Repo + regex is kept explicit to avoid arbitrary URL execution and impostor sites.
GITHUB_SOURCES = {
    "duckstation": {
        "repos": ["stenzek/duckstation"],
        "pattern": r"(?i)DuckStation.*x64.*\.AppImage$", "kind": "appimage",
        "binary_candidates": [], "prerelease": True,
    },
    "vita3k": {
        "repos": ["Vita3K/Vita3K"],
        "pattern": r"(?i).*Vita3K.*(x86_64|linux).*\.(AppImage|zip|tar\.gz)$", "kind": "auto",
        "binary_candidates": ["Vita3K", "vita3k"], "prerelease": True,
    },
    "shadps4": {
        "repos": ["shadps4-emu/shadPS4"],
        "pattern": r"(?i).*(linux|ubuntu|appimage).*\.(AppImage|tar\.gz|tar\.xz|zip)$",
        "kind": "auto", "binary_candidates": ["shadPS4", "shadps4", "shadPS4-qt"],
        "prerelease": True,
    },
    "rpcs3": {
        "repos": ["RPCS3/rpcs3-binaries-linux"],
        "pattern": r"(?i).*\.AppImage$", "kind": "appimage",
        "binary_candidates": [], "prerelease": True,
    },
    "pcsx2": {
        "repos": ["PCSX2/pcsx2"],
        "pattern": r"(?i).*(linux|appimage).*\.AppImage$", "kind": "appimage",
        "binary_candidates": [], "prerelease": True,
    },
    "xenia-canary": {
        "repos": ["xenia-canary/xenia-canary-releases", "xenia-canary/xenia-canary"],
        "pattern": r"(?i).*(canary|experimental).*\.zip$", "kind": "archive",
        "binary_candidates": ["xenia_canary.exe", "xenia.exe"], "prerelease": True,
    },
    "xemu": {
        "repos": ["xemu-project/xemu"],
        "pattern": r"(?i)xemu-[0-9][^-]*.*-x86_64\.AppImage$", "kind": "appimage",
        "binary_candidates": [], "prerelease": True,
    },
    "cemu": {
        "repos": ["cemu-project/Cemu"],
        "pattern": r"(?i).*\.AppImage$", "kind": "appimage",
        "binary_candidates": [], "prerelease": True,
    },
    "azahar": {
        "repos": ["azahar-emu/azahar"],
        "pattern": r"(?i).*azahar.*\.AppImage$", "kind": "appimage",
        "binary_candidates": [], "prerelease": True,
    },
    "melonds": {
        "repos": ["melonDS-emu/melonDS"],
        "pattern": r"(?i).*(linux|appimage|melonds).*\.AppImage$", "kind": "appimage",
        "binary_candidates": [], "prerelease": True,
    },
    "mgba": {
        "repos": ["mgba-emu/mgba"],
        "pattern": r"(?i).*(linux|appimage|mgba).*\.AppImage$", "kind": "appimage",
        "binary_candidates": [], "prerelease": True,
    },
    "mesen": {
        "repos": ["SourMesen/Mesen2"],
        "pattern": r"(?i).*(linux|appimage).*\.(AppImage|zip|tar\.gz)$", "kind": "auto",
        "binary_candidates": ["Mesen", "Mesen2"], "prerelease": True,
    },
}

# Stable Eden AppImage is served by the official Eden download infrastructure, not GitHub.
EDEN_RELEASES_PAGE = "https://git.eden-emu.dev/eden-emu/eden/releases"
EDEN_ASSET_RE = re.compile(
    r"https://stable\.eden-emu\.dev/(v[0-9][^\"'<> ]*)/Eden-Linux-v[^/\"'<> ]*-amd64-clang-pgo\.AppImage",
    re.I,
)
ALLOWED_ASSET_HOSTS = {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com", "stable.eden-emu.dev", "dl.dolphin-emu.org", "dolphin-emu.org", "www.dolphin-emu.org", "git.eden-emu.dev", "eden-emu.dev"}


def allowed_network_host(host: str) -> bool:
    host = host.lower().rstrip(".")
    # Exact hosts only. A wildcard for every *.github.com / *.githubusercontent.com
    # would unnecessarily trust unrelated subdomains if a lock or upstream response
    # were ever compromised.
    return host in ALLOWED_ASSET_HOSTS or host == "api.github.com"


def request(url: str, timeout: int = 60, accept: str = "application/vnd.github+json") -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not allowed_network_host(parsed.hostname or ""):
        raise ValueError(f"URL source non autorisée (HTTPS + hôte approuvé requis): {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        final = urllib.parse.urlparse(response.geturl())
        host = (final.hostname or "").lower()
        if final.scheme != "https" or not allowed_network_host(host):
            raise ValueError(f"Redirect vers hôte non autorisé: {response.geturl()}")
        data = response.read()
        if not data:
            raise ValueError(f"Asset vide: {url}")
        return data




def download_to_path(url: str, destination: Path, timeout: int = 240, max_bytes: int = 2_000_000_000) -> tuple[str, int]:
    """Stream a release asset to disk instead of retaining 50–200 MB in RAM."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not allowed_network_host(parsed.hostname or ""):
        raise ValueError(f"Refused URL download source (HTTPS + approved host required): {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/octet-stream"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    size = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            final = urllib.parse.urlparse(response.geturl())
            final_host = (final.hostname or "").lower()
            if final.scheme != "https" or not allowed_network_host(final_host):
                raise ValueError(f"Redirect to unapproved host: {response.geturl()}")
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes:
                raise ValueError(f"Asset exceeds configured size limit ({length} bytes)")
            with temp.open("wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(f"Asset exceeds configured size limit ({max_bytes} bytes)")
                    out.write(chunk)
                    digest.update(chunk)
        if size < 1024:
            raise ValueError(f"Asset too small ({size} bytes)")
        temp.replace(destination)
        return digest.hexdigest(), size
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def github_releases(repo: str) -> list[dict]:
    raw = request(f"{GITHUB_API}/repos/{repo}/releases?per_page=20")
    result = json.loads(raw.decode("utf-8"))
    if not isinstance(result, list):
        raise ValueError(f"Réponse GitHub inattendue pour {repo}")
    return result


def github_release_by_tag(repo: str, tag: str) -> dict:
    if not tag or len(tag) > 160 or "\n" in tag or "\r" in tag:
        raise ValueError("Invalid release tag in lockfile")
    url_tag = urllib.parse.quote(tag, safe="")
    raw = request(f"{GITHUB_API}/repos/{repo}/releases/tags/{url_tag}")
    result = json.loads(raw.decode("utf-8"))
    if not isinstance(result, dict) or result.get("tag_name") != tag:
        raise ValueError(f"Pinned release tag {tag!r} not found in {repo}")
    return result


def verify_github_checksum(repo: str, release: dict, asset_name: str, asset_path: Path, published_digest: str | None = None) -> tuple[bool, str]:
    actual = sha256_file(asset_path)
    if published_digest and published_digest.lower().startswith("sha256:"):
        expected = published_digest.split(":", 1)[1].lower()
        return actual == expected, f"sha256={actual}; GitHub API digest={expected}"
    assets = release.get("assets", [])
    checksum_assets = [a for a in assets if re.search(r"(sha256|sha-256|checksums?)", a.get("name", ""), re.I)
                       and a.get("browser_download_url")]
    for checksum in checksum_assets:
        try:
            content = request(checksum["browser_download_url"], timeout=40, accept="application/octet-stream").decode("utf-8", "replace")
        except Exception:
            continue
        for line in content.splitlines():
            if asset_name not in line:
                continue
            match = re.search(r"\b([a-fA-F0-9]{64})\b", line)
            if match:
                expected = match.group(1).lower()
                return actual == expected, f"sha256={actual}; expected={expected}"
    return True, f"sha256={actual}; no matching upstream checksum published (local hash only)"


def pick_asset(repo: str, spec: dict, pinned: dict | None = None) -> tuple[dict, dict] | None:
    pattern = re.compile(spec["pattern"])
    if pinned is not None:
        release = github_release_by_tag(repo, str(pinned.get("tag", "")))
        asset_name = str(pinned.get("asset", ""))
        candidates = [a for a in (release.get("assets") or [])
                      if a.get("name") == asset_name and a.get("browser_download_url")
                      and pattern.fullmatch(a.get("name", ""))]
        if len(candidates) != 1:
            raise ValueError(f"Pinned asset {asset_name!r} is absent or ambiguous in {repo}@{release.get('tag_name')}")
        return release, candidates[0]

    for release in github_releases(repo):
        if release.get("draft") or (release.get("prerelease") and not spec.get("prerelease", False)):
            continue
        assets = release.get("assets") or []
        # Prefer x86-64 assets. The regex is the main guardrail, followed by size/type checks.
        candidates = [a for a in assets if pattern.fullmatch(a.get("name", "")) and a.get("browser_download_url")]
        candidates = [a for a in candidates if not re.search(
            r"(arm64|aarch64|symbols|debug|(^|[-_.])dbg([-. _]|$)|sourcecode)",
            a.get("name", ""), re.I)]
        if candidates:
            candidates.sort(key=lambda a: (bool(re.search(r"(x86_64|x64|amd64)", a.get("name", ""), re.I)), a.get("size", 0)), reverse=True)
            return release, candidates[0]
    return None


def verify_locked_sha256(actual_sha256: str, lock_item: dict | None) -> None:
    if not lock_item:
        return
    expected = str(lock_item.get("sha256", "")).lower()
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("Pinned release asset is missing a valid SHA-256 in release-lock.json")
    if actual_sha256.lower() != expected:
        raise ValueError(f"Pinned SHA-256 mismatch: expected {expected}, got {actual_sha256}")


def safe_extract(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as zf:
            for member in zf.infolist():
                name = member.filename
                if name.startswith(("/", "\\")) or ".." in PurePosixPath(name.replace("\\", "/")).parts:
                    raise ValueError(f"Chemin dangereux dans ZIP: {name}")
                target = (destination / name).resolve()
                if root not in target.parents and target != root:
                    raise ValueError(f"Chemin ZIP hors destination: {name}")
            zf.extractall(destination)
            # zipfile does not consistently restore Unix executable bits. Apply only
            # ordinary file permissions; mark .exe files executable for Wine launch.
            for member in zf.infolist():
                extracted = destination / member.filename
                if not extracted.is_file():
                    continue
                stored_mode = (member.external_attr >> 16) & 0xFFFF
                is_executable = bool(stored_mode & 0o111) or extracted.suffix.lower() == ".exe"
                extracted.chmod(0o755 if is_executable else 0o644)
        return
    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, "r:*") as tf:
            members = []
            for member in tf.getmembers():
                name = member.name
                if name.startswith("/") or ".." in PurePosixPath(name).parts or member.issym() or member.islnk():
                    if member.isdir() is False and member.isfile() is False:
                        continue
                    if name.startswith("/") or ".." in PurePosixPath(name).parts:
                        raise ValueError(f"Chemin dangereux dans TAR: {name}")
                target = (destination / name).resolve()
                if root not in target.parents and target != root:
                    raise ValueError(f"Chemin TAR hors destination: {name}")
                members.append(member)
            tf.extractall(destination, members=members, filter="data")
        return
    raise ValueError(f"Format d'archive non supporté: {archive_path.name}")


def executable_files(directory: Path) -> list[Path]:
    files = []
    for path in directory.rglob("*"):
        if path.is_file() and os.access(path, os.X_OK):
            files.append(path)
    return files


def record(report: dict, identifier: str, status: str, **extra) -> None:
    report[identifier] = {"status": status, **extra}
    if status == "installed":
        print(f"[INSTALADO] {identifier}: {extra.get('version', 'upstream build')} — {extra.get('asset', extra.get('binary', 'binary'))}")
    else:
        print(f"[{status.upper()}] {identifier}: {extra.get('reason', '')}")


def get_spec_for_id(identifier: str) -> dict | None:
    return GITHUB_SOURCES.get(identifier)


def install_github_asset(identifier: str, spec: dict, target: Path, catalog_by_id: dict, report: dict,
                         lock_item: dict | None = None, strict_lock: bool = False) -> bool:
    """Install one official release, optionally pinned to an exported lock entry."""
    problems = []
    item = catalog_by_id[identifier]
    if strict_lock and (not lock_item or lock_item.get("mode") != "pinned"):
        record(report, identifier, "skipped-by-lock", reason="no pinned upstream asset in strict release-lock.json")
        return False
    if lock_item and lock_item.get("mode") == "pinned":
        locked_repo = lock_item.get("repo")
        if locked_repo not in spec["repos"]:
            record(report, identifier, "failed", reason="pinned repo is not in the official source allowlist")
            return False
        repos = [locked_repo]
    else:
        repos = spec["repos"]
    for repo in repos:
        try:
            picked = pick_asset(repo, spec, lock_item if lock_item and lock_item.get("mode") == "pinned" else None)
            if not picked:
                problems.append(f"{repo}: sem asset que combine com {spec['pattern']}")
                continue
            release, asset = picked
            asset_name = asset["name"]
            appimage = spec["kind"] == "appimage" or asset_name.lower().endswith(".appimage")

            with tempfile.TemporaryDirectory(prefix="emustack-download-") as td:
                archive = Path(td) / asset_name
                asset_hash, asset_size = download_to_path(
                    asset["browser_download_url"], archive, timeout=300,
                    max_bytes=2_000_000_000,
                )
                if asset_size < 1024:
                    raise ValueError(f"Asset pequeno/suspeito ({asset_size} bytes)")
                ok, checksum_info = verify_github_checksum(repo, release, asset_name, archive, asset.get("digest"))
                if not ok:
                    record(report, identifier, "failed", reason=f"SHA-256 divergente: {checksum_info}", repo=repo, asset=asset_name)
                    return False
                try:
                    verify_locked_sha256(asset_hash, lock_item if lock_item and lock_item.get("mode") == "pinned" else None)
                except ValueError as exc:
                    record(report, identifier, "failed", reason=str(exc), repo=repo, asset=asset_name, sha256=asset_hash)
                    return False

                if appimage:
                    alias = next((n for n in item.get("binary_names", []) if n.lower().endswith(".appimage")), identifier + ".AppImage")
                    output = target / alias
                    temp_output = output.with_suffix(output.suffix + ".verified-part")
                    shutil.copyfile(archive, temp_output)
                    temp_output.chmod(0o755)
                    temp_output.replace(output)
                    record(report, identifier, "installed", version=release.get("tag_name", "unknown"), repo=repo,
                           asset=asset_name, url=asset["browser_download_url"], sha256=asset_hash,
                           size_bytes=asset_size, checksum=checksum_info, binary=str(output))
                    return True

                # Archives are extracted to a dedicated directory with traversal protection.
                project_dir = target / (identifier + "-payload")
                if project_dir.exists():
                    shutil.rmtree(project_dir)
                safe_extract(archive, project_dir)

            binaries = executable_files(project_dir)
            candidates = [p for name in spec.get("binary_candidates", [])
                          for p in binaries if p.name.lower() == name.lower()]
            if not candidates:
                candidates = [p for p in binaries
                              if not re.search(r"(unins|updat|crashpad|helper|symbols|\.dll$)", p.name, re.I)]
            if not candidates:
                record(report, identifier, "failed", reason="archive downloaded but no executable file was found",
                       repo=repo, asset=asset_name, checksum=checksum_info)
                return False
            selected = candidates[0]
            aliases = item.get("binary_names", [])
            alias = next((n for n in aliases if not n.lower().endswith(".appimage")), selected.name)
            alias_path = target / alias
            if alias_path.exists() or alias_path.is_symlink():
                alias_path.unlink()
            # The target is a relative link within /opt/emustack/installed.
            alias_path.symlink_to(selected.relative_to(target))
            record(report, identifier, "installed", version=release.get("tag_name", "unknown"), repo=repo,
                   asset=asset_name, url=asset["browser_download_url"], sha256=asset_hash,
                   size_bytes=asset_size, checksum=checksum_info, binary=str(alias_path))
            return True
        except urllib.error.HTTPError as exc:
            problems.append(f"{repo}: HTTP {exc.code}")
        except Exception as exc:
            problems.append(f"{repo}: {type(exc).__name__}: {exc}")
    record(report, identifier, "not-available", reason="; ".join(problems) or "no official release asset matched")
    return False


def _locked_url(lock_item: dict, expected_mode: str) -> tuple[str, str]:
    if lock_item.get("mode") != expected_mode:
        raise ValueError(f"Expected lock mode {expected_mode!r}")
    url = str(lock_item.get("url", ""))
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not allowed_network_host(parsed.hostname or ""):
        raise ValueError("Pinned URL is not on an approved HTTPS host")
    return url, str(lock_item.get("version", "locked"))


def install_eden(target: Path, report: dict, catalog_by_id: dict, lock_item: dict | None = None,
                 strict_lock: bool = False) -> bool:
    try:
        if strict_lock and (not lock_item or lock_item.get("mode") != "pinned-url"):
            record(report, "eden", "skipped-by-lock", reason="no pinned official Eden asset in strict release-lock.json")
            return False
        if lock_item and lock_item.get("mode") == "pinned-url":
            url, version = _locked_url(lock_item, "pinned-url")
        else:
            page = request(EDEN_RELEASES_PAGE, timeout=45, accept="text/html,*/*").decode("utf-8", "replace")
            urls = []
            for match in EDEN_ASSET_RE.finditer(page.replace("&amp;", "&")):
                url = match.group(0)
                if url not in urls:
                    urls.append(url)
            if not urls:
                alt = re.findall(r"https://stable\.eden-emu\.dev/[^\"'<> ]*Eden-Linux-v[^/\"'<> ]*-amd64-clang-pgo\.AppImage", page, re.I)
                urls = list(dict.fromkeys(alt))
            if not urls:
                record(report, "eden", "not-available", reason="no official amd64 AppImage link parsed from the upstream release page")
                return False
            url = urls[0]
            version = Path(urllib.parse.urlparse(url).path).name
        item = catalog_by_id["eden"]
        alias = next((n for n in item.get("binary_names", []) if n.lower().endswith(".appimage")), "eden.AppImage")
        output = target / alias
        candidate = output.with_suffix(output.suffix + ".verified-part")
        try:
            asset_hash, asset_size = download_to_path(url, candidate, timeout=300)
            if lock_item and lock_item.get("mode") == "pinned-url":
                verify_locked_sha256(asset_hash, lock_item)
            if asset_size < 1024 * 1024:
                raise ValueError(f"Downloaded asset too small: {asset_size} bytes")
            candidate.chmod(0o755)
            candidate.replace(output)
        finally:
            candidate.unlink(missing_ok=True)
        checksum_text = "SHA-256 matched release lock" if lock_item and lock_item.get("mode") == "pinned-url" else "SHA-256 local only; no upstream checksum verifier wired"
        record(report, "eden", "installed", version=version, asset=Path(urllib.parse.urlparse(url).path).name,
               url=url, sha256=asset_hash, size_bytes=asset_size, checksum=checksum_text, binary=str(output))
        return True
    except Exception as exc:
        record(report, "eden", "failed", reason=f"{type(exc).__name__}: {exc}")
        return False


def install_dolphin_appimage(target: Path, report: dict, catalog_by_id: dict, lock_item: dict | None = None,
                             strict_lock: bool = False) -> bool:
    try:
        if strict_lock and (not lock_item or lock_item.get("mode") != "pinned-url"):
            record(report, "dolphin", "skipped-by-lock", reason="no pinned official Dolphin asset in strict release-lock.json")
            return False
        if lock_item and lock_item.get("mode") == "pinned-url":
            url, version = _locked_url(lock_item, "pinned-url")
        else:
            page_url = "https://dolphin-emu.org/download/dev/"
            page = request(page_url, timeout=45, accept="text/html,*/*").decode("utf-8", "replace")
            links = re.findall(r"https://dl\.dolphin-emu\.org/[^\"'<> ]+\.AppImage", page, re.I)
            links = [u for u in dict.fromkeys(links) if re.search(r"x64\.AppImage$", u, re.I) and not re.search(r"arm64", u, re.I)]
            if not links:
                record(report, "dolphin", "not-available", reason="official development page did not expose an x64 AppImage; apt package fallback is used if present")
                return False
            url = links[0]
            version = Path(urllib.parse.urlparse(url).path).name
        alias = "Dolphin.AppImage"
        output = target / alias
        candidate = output.with_suffix(output.suffix + ".verified-part")
        try:
            asset_hash, asset_size = download_to_path(url, candidate, timeout=300)
            if lock_item and lock_item.get("mode") == "pinned-url":
                verify_locked_sha256(asset_hash, lock_item)
            if asset_size < 1024 * 1024:
                raise ValueError("Dolphin AppImage download is suspiciously small")
            candidate.chmod(0o755)
            candidate.replace(output)
        finally:
            candidate.unlink(missing_ok=True)
        checksum_text = "SHA-256 matched release lock" if lock_item and lock_item.get("mode") == "pinned-url" else "SHA-256 local only; upstream page does not expose a matching checksum"
        record(report, "dolphin", "installed", version=version, asset=alias,
               url=url, sha256=asset_hash, size_bytes=asset_size, checksum=checksum_text, binary=str(output))
        return True
    except Exception as exc:
        record(report, "dolphin", "not-available", reason=f"official AppImage download failed ({type(exc).__name__}: {exc}); apt package fallback is used if present")
        return False

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="/opt/emustack/installed", type=Path)
    parser.add_argument("--catalog", default="/opt/emustack/catalog.json", type=Path)
    parser.add_argument("--report", default="/opt/emustack/install-report.json", type=Path)
    parser.add_argument("--lock", default=Path("/opt/emustack/release-lock.json"), type=Path)
    parser.add_argument("--skip-network", action="store_true")
    args = parser.parse_args()
    args.target.mkdir(parents=True, exist_ok=True)
    data = json.loads(args.catalog.read_text(encoding="utf-8"))
    by_id = {x["id"]: x for x in data["emulators"]}
    report: dict[str, dict] = {}
    if args.lock.is_file():
        try:
            lock_data = json.loads(args.lock.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"release-lock.json contém JSON inválido: {exc}")
        if (not isinstance(lock_data, dict) or lock_data.get("schema_version") != 1
                or not isinstance(lock_data.get("items", {}), dict)
                or not isinstance(lock_data.get("strict", False), bool)
                or not all(isinstance(value, dict) for value in lock_data.get("items", {}).values())):
            raise SystemExit("release-lock.json inválido: schema_version=1, strict booleano e items como objeto de objetos são necessários.")
    else:
        lock_data = {"schema_version": 1, "strict": False, "items": {}}
    lock_items = lock_data.get("items", {})
    strict_lock = lock_data.get("strict", False)

    # Binaries built into the image from apt packages are checked separately by `emustack list`.
    for identifier, spec in GITHUB_SOURCES.items():
        if identifier in by_id and not args.skip_network:
            install_github_asset(identifier, spec, args.target, by_id, report,
                                 lock_items.get(identifier), strict_lock)
    if not args.skip_network:
        install_eden(args.target, report, by_id, lock_items.get("eden"), strict_lock)
        install_dolphin_appimage(args.target, report, by_id, lock_items.get("dolphin"), strict_lock)

    # Never manufacture fake launchers for projects that do not publish a runnable emulator binary.
    record(report, "xbox-one", "unsupported-no-runner",
           reason="no supported, full-system Xbox One emulator/runner is integrated; launches are deliberately blocked")
    record(report, "xbox-series", "unsupported-no-runner",
           reason="no supported Xbox Series S/X emulator/runner is integrated; launches are deliberately blocked")
    kyty_launcher = next((p for p in (args.target / "kytyps5").rglob("kyty_launcher") if p.is_file() and os.access(p, os.X_OK)), None)
    if kyty_launcher:
        record(report, "kytyps5", "installed", version="source build", repo="KytyPS5/KytyPS5", binary=str(kyty_launcher),
               details="built from the official source in the Docker build stage")
    else:
        record(report, "kytyps5", "not-available", reason="the optional source build did not produce kyty_launcher; see Docker build logs")

    # Record packages that APT actually installed, including fallback packages after
    # a release endpoint did not offer a matching standalone asset.
    for identifier, item in by_id.items():
        if report.get(identifier, {}).get("status") == "installed":
            continue
        for command in item.get("commands", []):
            path = shutil.which(command)
            if path:
                record(report, identifier, "installed", version="Debian package", source="APT fallback", binary=path,
                       details="Executable is available on PATH. This confirms installation only, not game compatibility.")
                break
        if identifier not in report:
            report[identifier] = {"status": "not-available", "reason": "no upstream download or APT executable detected"}
    payload = {
        "project": "EmuStack",
        "version": "0.7.1",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "important": "A download/build status is not proof that every game works. No games, BIOS, firmware, keys, or copyrighted system files are bundled.",
        "items": report,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    installed = sum(1 for v in report.values() if v.get("status") == "installed")
    print(f"\nEmuStack: {installed} project(s) reported installed/downloaded/built (including APT fallbacks). Detailed report: {args.report}")
    print("Some catalog entries intentionally remain unavailable: not all twenty names correspond to a distributable emulator binary.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
