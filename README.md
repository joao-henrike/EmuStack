# EmuStack

Private repository for the EmuStack console-emulation orchestrator.

## Import the verified 0.7.0 source bundle

The initial repository commit contains this bootstrap README. Download `EmuStack-Docker-0.7.0.zip` from the ChatGPT conversation to your local machine, clone this private repository, then run:

```bash
chmod +x IMPORT-LOCAL.sh
./IMPORT-LOCAL.sh ~/Downloads/EmuStack-Docker-0.7.0.zip
```

The importer checks the archive SHA-256, verifies its structure, copies the project source tree, removes itself from the resulting source tree, commits the import, and pushes it to `main`. It refuses to run from a different GitHub remote or a dirty working tree. GitHub authentication must be configured locally for `git push`.

The bundle does not include games, ROMs, console BIOS/firmware, NAND, HDD images or encryption keys. Do not commit `.env`, local saves or proprietary system files.
