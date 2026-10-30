# Changelog

> **EMUSTACK // GAMING LAB** · [Visão geral](README.md) · [Identidade visual](docs/IDENTIDADE-VISUAL.md) · [Documentação](docs/INSTALLATION.md) · [Roadmap](docs/ROADMAP-STATUS.md)

## 0.7.1 post-release hardening — 2026-10-28

- Restrict dashboard GET/POST access from the 20 isolated agents using a TCP source allowlist and deterministic per-network IPAM.
- Add live runtime probes that attempt state-changing requests from each agent with spoofed HTTP headers.
- Fix Debian package selection to require a real APT install candidate; add an image build check in CI without optional upstream downloads.
- Commit a strict SHA-256 lock for 11 verified official emulator assets and explicit skip reasons for nine unavailable/unpinned entries; add a tested workflow to refresh the lock and rebuild strictly.
- Clarify that the current strict lock covers downloadable official assets only; KytyPS5 source compilation is not claimed by this lock or the default acceptance run.
- Keep Docker runtime acceptance and game/system boot validation as explicit host-side requirements.

## 0.7.1 — catalog of authorized game-content sources

- Expanded `game-sources.json` with per-environment guidance for all 20 profiles and source links for creator-published homebrew, demos, official storefronts and rights guidance.
- Added filters by source category and console to the dashboard Sources view.
- Made the key distinction explicit: emulator repositories publish emulator code/releases, not commercial game files; EmuStack does not automatically fetch or install game content.
- Added regression tests for the 20 console mappings, referential integrity, HTTPS source links, rights notices and disabled automatic downloads.
- Source catalog entries are discovery pointers, not a blanket legality or compatibility guarantee. Verify rights and format on each individual release.

## Source catalog update — 2026-10-28

- Expanded `game-sources.json` with source descriptions, rights guidance and a per-environment map for all 20 profiles.
- Added homebrew/demos discovery sources including PDRoms, itch.io homebrew/ NES-ROM filters, the official PPSSPP demo/homebrew guide, GameBrew and creator-published GitHub projects.
- Added a console filter to the Sources view and per-console warnings about formats, firmware prerequisites and unsupported/full-system limitations.
- Clarified that emulator repositories publish emulator code/binaries and that EmuStack does not automatically download commercial games or provide unauthorized ROM sources.
- Verified source URLs through search results; individual rights, compatibility and file formats still require per-item review.

## 0.7.0 — last pre-host-validation engineering pass

- Added real runtime probes for X11/XWayland reachability, PulseAudio/PipeWire Pulse compatibility, Vulkan device enumeration, detection of software-only rendering, and explicitly mapped read-only controller devices.
- Added opt-in strict gates (`EMUSTACK_REQUIRE_GUI`, `EMUSTACK_REQUIRE_AUDIO`, `EMUSTACK_REQUIRE_VULKAN`, `EMUSTACK_REQUIRE_GPU`, `EMUSTACK_REQUIRE_INPUT`) and a sanitized acceptance report at `data/runtime-acceptance.json`.
- Installed `pulseaudio-utils` when the Debian repository provides it, enabling `pactl info` as an audio connectivity test.
- Updated PSP capability documentation to describe VSH/XMB as experimental and firmware-dependent, not guaranteed.
- Automated validation on this source tree: 75 Python tests, 13 JavaScript launch tests, 11 static UI assertions; Compose YAML parsed and service/network counts cross-checked. A Docker build and hardware boot were not run in this environment.

## 0.6.0 — 2026-10-28

- Rebuilt the profile set around 20 distinct runtime IDs. Removed duplicate/research-only Xbox/PS5 profiles and added PS1/DuckStation, PSP/PPSSPP and PS Vita/Vita3K. Xbox One and Xbox Series remain deliberately blocked placeholders without runnable commands.
- Added DuckStation BIOS-shell route where a user-provided PS1 BIOS is detected.
- Bound the original Xbox dashboard confirmation to the SHA-256 and configured container path of the user HDD; documented that this remains an operator attestation, not an automatic content scan.
- Added per-environment storage inspection, SHA-256 snapshot backup/restore, rollback preservation, and blank `qcow2`/`raw` data-disk creation.
- Added host diagnostics and runtime acceptance checks for agent/network/mount separation.
- Added environment-root and mounted-path symlink rejection to preserve data separation.
- Pinned the official Debian multi-platform base-image digest; added an optional dated Debian APT snapshot mode and upstream release-lock workflow.
- Rewrote capability documentation to clearly distinguish profile availability, game emulation, firmware/menu boot, manual paths and unsupported systems.
- Automated suite: 66 Python tests, 13 JavaScript launch tests, 11 static UI assertions. This does not substitute for a Docker build or on-host emulator tests.
