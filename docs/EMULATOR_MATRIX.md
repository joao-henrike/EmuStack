# Matriz de runtime e boot — EmuStack 0.7.1

> **EMUSTACK // GAMING LAB** · [README](../README.md) · [Instalação](INSTALLATION.md) · [Guia do usuário](USER_GUIDE.md) · [Matriz de emuladores](EMULATOR_MATRIX.md) · [Segurança](SECURITY.md) · [Identidade visual](IDENTIDADE-VISUAL.md)

A matriz distingue quatro coisas que não devem ser confundidas: perfil listado, binário instalado, jogos que o upstream consegue executar e boot do sistema/menu original. O `install-report.json` gerado no host é a fonte para confirmar quais binários foram encontrados. Nenhum perfil é declarado plenamente funcional apenas por estar no catálogo.

| Perfil | Plataforma | Alvo de emulação | Boot de sistema/menu original | Estado de confiança |
|---|---|---|---|---|
| `kytyps5` | PS5 | Projeto experimental/build opcional | Não suportado | Pesquisa; nenhuma alegação de sistema completo |
| `shadps4` | PS4 | Jogos experimentais compatíveis | Não suportado | Jogos dependem do upstream |
| `rpcs3` | PS3 | Jogos e VSH/XMB | Rota condicional; precisa firmware instalado e teste real | Parcial/condicional |
| `duckstation` | PS1 | Jogos e BIOS shell | `-bios` quando BIOS válido é detectado | Condicional; binário Linux pode não estar disponível automaticamente |
| `pcsx2` | PS2 | Jogos e BIOS Browser | Rota condicional com BIOS configurado | Condicional |
| `ppsspp` | PSP | Jogos e tentativa VSH/XMB via `--vsh` | Experimental; requer firmware `flash0` e PPSSPP compatível | Experimental; boot visual ainda precisa ser comprovado |
| `vita3k` | PS Vita | Jogos/homebrew compatíveis | A interface Vita3K não é o LiveArea original | Experimental/focado em jogos |
| `xbox-one` | Xbox One | Nenhum runner | Não suportado | Bloqueado intencionalmente |
| `xenia-canary` | Xbox 360 | Jogos compatíveis conforme binário/plataforma | Dashboard retail não suportado | Condicional; no catálogo atual a rota pode depender de Wine |
| `xbox-series` | Xbox Series S/X | Nenhum runner | Não suportado | Bloqueado intencionalmente |
| `xemu` | Xbox original | Hardware emulado com arquivos do usuário | Pode depender de BIOS/MCPX/HDD configurados; dashboard retail exige verificação manual | A atestação é uma declaração vinculada ao SHA-256, não inspeção do HDD |
| `eden` | Switch | Jogos experimentais quando runner disponível | HOME Menu integral não suportado neste perfil | Experimental |
| `cemu` | Wii U | Jogos | Wii U Menu depende de MLC e `men.rpx` válidos | Condicional |
| `dolphin` | Wii/GameCube | Jogos | Wii Menu depende de NAND/System Menu; GameCube IPL depende de configuração | Condicional/manual |
| `azahar` | Nintendo 3DS/2DS | Jogos | HOME Menu manual no emulador | Manual |
| `melonds` | Nintendo DS | Jogos | Firmware/menu depende de configuração suportada | Manual/condicional |
| `mgba` | GB/GBC/GBA | Jogos/sequência de boot | Não há dashboard moderno equivalente | Focado em jogos |
| `mupen64plus` | Nintendo 64 | Jogos | Não há dashboard moderno equivalente | Focado em jogos |
| `bsnes` | Super Nintendo | Jogos | Não há dashboard moderno equivalente | Focado em jogos |
| `mesen` | NES e clássicos | Jogos | Não há dashboard moderno equivalente | Focado em jogos |

## Rotas de sistema originais declaradas

- **PS1/DuckStation:** shell de BIOS somente com BIOS válido e detectado; execução gráfica precisa ser testada no host.
- **PS2/PCSX2:** Browser/System Configuration do BIOS, condicionado ao BIOS e à configuração.
- **PS3/RPCS3:** VSH/XMB, condicionado ao firmware instalado e ao módulo VSH.
- **PSP/PPSSPP:** VSH/XMB experimental via `--vsh`, condicionado ao firmware e à versão do PPSSPP; não é certificado como estável.
- **Xbox original/xemu:** valida arquivos apontados por `xemu.toml`, confere o hash da imagem HDD e exige atestação explícita. A atestação não analisa o conteúdo interno do HDD.
- **Wii/Dolphin:** tentativa de boot do Wii System Menu se instalado no NAND persistente.
- **Wii U/Cemu:** tentativa de boot do Wii U Menu com MLC/sistema configurados.

Essas rotas são código de integração e checagens de pré-requisitos; não são evidência de boot real em todos os hosts. A aceitação do runtime confere a topologia Docker e endpoints, mas não inicia todos os sistemas/jogos.

## Recursos de infraestrutura

GPU NVIDIA pode ser exposta com `compose.nvidia.yaml`; display/áudio são opt-in no `host-setup.sh`; um dispositivo de controle explicitamente selecionado pode ser encaminhado a um único ambiente. O script de aceitação agora pode testar essas rotas no runtime do host. Todos compartilham o kernel do host, mas não seus dados persistentes. A disponibilidade real depende do emulador e dos drivers do host.

## Build/lock

`release-lock.json` controla assets upstream suportados. O digest multi-arquitetura do Debian base está fixado no Dockerfile. `FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh` tenta capturar assets oficiais baixados e hashes verificados. Para resolver APT num snapshot datado, use `APT_SNAPSHOT_TIMESTAMP=20261027T000000Z FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh`. Um snapshot congela também as correções de segurança; atualize-o conscientemente. Ainda não há garantia de build bit-a-bit em qualquer arquitetura/ambiente.
