# Build reproducibility and update policy

## Debian base image

The Dockerfile pins the multi-platform manifest digest for the official `debian:trixie-slim` image observed on 2026-10-28:

`sha256:89c1ea91e897f0fe0a3731595330bc45b8bdef4047464a07116f891a94054b31`

Reference: [official Debian image tags on Docker Hub](https://hub.docker.com/_/debian/tags/). A digest is immutable; the project should update this value only after reviewing a new official digest and security status.

## Debian package repository

By default, APT uses the current Trixie repositories so rebuilds receive current package/security updates. Thus package versions can change between builds even though the base image is pinned. To use a fixed archive snapshot, set `APT_SNAPSHOT_TIMESTAMP` to a Debian snapshot ID, for example:

```bash
APT_SNAPSHOT_TIMESTAMP=20261027T000000Z FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh
```

The snapshot mode switches both Debian and Debian Security sources to the dated snapshot and disables `Valid-Until` checking as documented for Debian snapshots. This is intended for controlled/reproducible builds, not as a permanent security update policy: the selected date also freezes security fixes. Update the timestamp after reviewing subsequent patches. See the [official Debian snapshot documentation](https://snapshot.debian.org/).

## Upstream emulator assets

The committed `release-lock.json` is strict and covers all 20 catalog IDs. The current verified lock pins 11 downloadable official assets with SHA-256; the other 9 entries are explicitly marked `skip-upstream` with reasons instead of claiming binaries that were not verified. The lock was generated from a successful online build and a second build using the resulting strict lock completed successfully.

The successful lock-generation run disabled the optional KytyPS5 source build (`BUILD_KYTYPS5=0`), so KytyPS5 is correctly marked `skip-upstream` in this lock. When explicitly enabled, the Dockerfile checks a declared KytyPS5 tag/short commit before attempting compilation; that separate source-build path is not covered by the downloadable-asset lock and is not claimed as built by the current acceptance run.

### Explicitly skipped upstream entries

Every `skip-upstream` entry is intentional and must remain explicit until there is verifiable provenance. The skip is not a statement that the emulator can never be installed; a separately trusted distro package may be detected, but this lock does not certify that path.

| Profile | Current decision | Next action before changing the lock |
|---|---|---|
| `kytyps5` | `skip-upstream` | Pin source commit, toolchain and build inputs; capture the resulting artifact hash in a separate reviewed build path. |
| `shadps4` | `skip-upstream` | Resolve official Linux artifact or reproducible source build and record exact SHA-256 before enabling download. |
| `ppsspp` | `skip-upstream` | Capture an exact official Linux asset and verify SHA-256; otherwise rely only on separately detected trusted packages/user binaries. |
| `xbox-one` | `skip-upstream` | Remain intentionally blocked until a credible full-system runner and verifiable build/package exist. |
| `xbox-series` | `skip-upstream` | Remain intentionally blocked until a credible full-system runner and verifiable build/package exist. |
| `dolphin` | `skip-upstream` | Capture an exact official Linux asset and verify SHA-256; otherwise rely only on separately detected trusted packages/user binaries. |
| `melonds` | `skip-upstream` | Capture an exact official Linux artifact and verify SHA-256; no guessed filenames or substitutions. |
| `mupen64plus` | `skip-upstream` | Capture an exact official Linux artifact and verify SHA-256; no guessed filenames or substitutions. |
| `bsnes` | `skip-upstream` | Capture an exact official Linux artifact and verify SHA-256; no guessed filenames or substitutions. |

To refresh official assets, run the GitHub Actions workflow **Freeze official emulator release assets**. It starts with an empty, non-strict lock in the temporary runner workspace to discover current official releases, then exports a candidate, validates coverage and hashes, attempts a strict rebuild, and uploads the candidate as an artifact. Review the downloaded artifact before replacing the committed lock. Do not remove explicit `skip-upstream` reasons simply to make the catalog appear complete.

The Debian base image digest is pinned, but Debian APT package versions remain time-dependent unless `APT_SNAPSHOT_TIMESTAMP` is set. The strict release lock is not a byte-for-byte reproducibility guarantee.

## Remaining limits

This improves repeatability but does not promise byte-identical output across CPU architectures, Docker/BuildKit versions, build flags, or upstream build systems. Some builds are experimental and may fail. Run `scripts/validate-project.sh`, then build and run `scripts/runtime-acceptance.sh` on the target Docker host. The runtime acceptance test checks topology and API behavior, not all games/firmware boot.
