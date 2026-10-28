# EmuStack

Private repository for the EmuStack console-emulation orchestrator.

## Import the verified 0.7.0 source bundle

Download [`EmuStack-Docker-0.7.0.zip`](sandbox:/mnt/data/EmuStack-Docker-0.7.0.zip) from the ChatGPT conversation to your computer. Then clone this private repository and run the importer with Bash (do not `chmod` it first, so the working tree remains clean):

```bash
gh auth login
gh auth setup-git
git clone https://github.com/joao-henrike/EmuStack.git
cd EmuStack
bash IMPORT-LOCAL.sh ~/Downloads/EmuStack-Docker-0.7.0.zip
```

The importer verifies the archive's SHA-256, validates the ZIP and expected source layout, refuses an unexpected Git remote or dirty working tree, and rejects `.env`, key files, BIOS/firmware, games, saves, and other user data before staging. It prints a staged diff summary and asks for confirmation before committing and pushing the project to `main`.

Expected archive SHA-256:

```text
c503808f3b833177dc9115c0b8e2c8e68c93726e4c4c4c2a15cb9daf63e3067f
```

The bundle does not include games, ROMs, console BIOS/firmware, NAND, HDD images or encryption keys. Never commit local `.env`, proprietary system files or personal saves.
