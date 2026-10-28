# EmuStack

Private repository for the EmuStack console-emulation orchestrator.

## Current source bundle

The latest bundle prepared in this conversation is **EmuStack 0.7.1**. Download `EmuStack-Docker-0.7.1.zip` from the ChatGPT conversation, then clone this private repository and run the guarded importer:

```bash
gh auth login
gh auth setup-git
git clone https://github.com/joao-henrike/EmuStack.git
cd EmuStack
bash IMPORT-LOCAL.sh ~/Downloads/EmuStack-Docker-0.7.1.zip
```

The importer validates the SHA-256, ZIP and source layout, refuses an unexpected Git remote or dirty tree, rejects secrets and locally supplied games/firmware, shows a staged diff, and asks for confirmation before committing and pushing the full source tree to `main`.

Expected bundle SHA-256:

```text
3753467d99c7ef1e73cce9d1fc0262b60a2a95bc83804994ea35b1b66ce97771
```

## Game-content sources

See [docs/GAME_SOURCES.md](docs/GAME_SOURCES.md) for the per-console source list. The 0.7.1 source bundle also includes `game-sources.json` and dashboard filters by category and console.

Important distinction: emulator repositories ordinarily distribute emulator code/releases, not commercial games. The sources list contains homebrew/demo discovery, official storefront information and rights guidance; it does not list unauthorized commercial ROM/ISO download sites. EmuStack does not automatically download or install games.

The bundle does not include games, ROMs, BIOS, firmware, NAND, HDD images, encryption keys or private `.env` configuration. Never commit proprietary system files or personal saves.
