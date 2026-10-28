# EmuStack

**Status do repositório:** este clone contém apenas o bootstrap e a documentação de fontes neste momento. O código-fonte completo do EmuStack 0.7.1 ainda precisa ser importado a partir do ZIP verificado abaixo. Não trate esta branch como a árvore de código completa até que apareçam `Dockerfile`, `compose.yaml`, `emustack.py`, `scripts/`, `tests/` e `web/`.

## Importar o projeto completo 0.7.1

1. Baixe `EmuStack-Docker-0.7.1.zip` da conversa.
2. Configure o GitHub CLI e clone este repositório privado.
3. Execute o importador, que verifica o checksum, a estrutura e arquivos locais antes de criar um commit e enviar para `main`.

```bash
gh auth login
gh auth setup-git
git clone https://github.com/joao-henrike/EmuStack.git
cd EmuStack
bash IMPORT-LOCAL.sh ~/Downloads/EmuStack-Docker-0.7.1.zip
```

O importador exige um repositório limpo, confirma o remote esperado, rejeita segredos, jogos, BIOS/firmware e saves locais, apresenta a lista das mudanças e pede confirmação antes do commit/push.

SHA-256 esperado:

```text
3753467d99c7ef1e73cce9d1fc0262b60a2a95bc83804994ea35b1b66ce97771
```

## Fontes de jogos

Consulte [docs/GAME_SOURCES.md](docs/GAME_SOURCES.md) para a lista organizada por console, com homebrew, demos, lojas oficiais e avisos de licença. O ZIP 0.7.1 inclui `game-sources.json` e os filtros do dashboard por categoria e plataforma.

Repositórios como RPCS3, PCSX2, Dolphin, PPSSPP e Xenia normalmente distribuem emuladores, não jogos comerciais. O EmuStack não baixa nem redistribui ROMs/ISOs comerciais, BIOS, firmware, NAND, imagens de HDD ou chaves. Nunca faça commit de arquivos proprietários, saves pessoais ou `.env` local.
