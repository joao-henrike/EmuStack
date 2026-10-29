# EmuStack 0.7.1

**EmuStack é um orquestrador local de ambientes de emulação**, com um agente e uma raiz de dados por perfil. Ele não é um emulador universal nem transforma um projeto experimental em um console funcional. O objetivo desta versão é tornar a separação de dados, a detecção de capacidades, o armazenamento, os diagnósticos e a aceitação em runtime explícitos e auditáveis.

> **Limite essencial:** 20 perfis (e 21 alvos de interface/sistema documentados) não significam 20 consoles integralmente emulados. Um perfil pode representar emulação de jogos, boot parcial de BIOS/menu, um fluxo manual ou um ambiente deliberadamente bloqueado por não haver runner confiável. Não existe dashboard HTML que finja ser a interface original.

## O que foi acrescentado nesta versão

- 20 agentes/ambientes com tokens e redes internas distintos.
- Catálogo atualizado, removendo perfis redundantes ou sem runner verificável e adicionando PlayStation 1 (DuckStation), PSP (PPSSPP) e PS Vita (Vita3K).
- Xbox One e Xbox Series mantidos como perfis explícitos **não suportados/bloqueados**, sem tentativa de iniciar um binário aleatório.
- Verificação de symlinks nas raízes de ambientes, validação do path de jogos e recusa de restaurações de snapshots de outro ambiente.
- Ferramenta de inventário, backup e restore transacional de um ambiente, com manifesto e verificação SHA-256 por arquivo.
- Criação opcional de discos `qcow2`/`raw` vazios dentro do ambiente escolhido. Um disco vazio **não** contém firmware, partições de console, sistema operacional ou dashboard.
- Diagnóstico read-only do host (Docker/Compose, RAM, NVIDIA, Vulkan, display, áudio, controles e `qemu-img`).
- Attestation do HDD do Xbox original vinculada ao seu SHA-256. Essa atestação registra a declaração explícita do operador; não é análise automática do conteúdo do HDD.
- Digest da imagem base Debian fixado e opção de selecionar um snapshot APT datado. APT pode continuar seguindo os repositórios atuais por padrão para receber atualizações; o snapshot aumenta a reprodutibilidade mas congela também as correções de segurança nessa data. O lock upstream fixa hashes dos assets baixados quando o congelamento é executado. Isso ainda não promete build bit-a-bit em todas as arquiteturas/ambientes.
- Teste de aceitação de runtime para conferir serviços, redes, mounts e capacidades opcionais de tela, áudio, Vulkan/GPU e controle no host.

## Matriz de perfis

| ID | Plataforma | O que o perfil pretende fazer | Boot original integrado |
|---|---|---|---|
| `kytyps5` | PS5 | Projeto experimental, se um binário for construído | **Não suportado** |
| `shadps4` | PS4 | Jogos compatíveis experimentais | **Não suportado** |
| `rpcs3` | PS3 | Jogos; iniciar VSH/XMB quando firmware estiver instalado | Condicional, requer teste real |
| `duckstation` | PS1 | Jogos; shell de BIOS com BIOS válido | Condicional, `-bios` |
| `pcsx2` | PS2 | Jogos; Browser/System Configuration do BIOS | Condicional |
| `ppsspp` | PSP | Jogos; tentativa experimental de VSH/XMB via `--vsh` | Experimental; requer firmware e binário compatível |
| `vita3k` | PS Vita | Jogos/homebrew compatíveis quando disponíveis | **Não**: interface própria não é LiveArea autêntico |
| `xbox-one` | Xbox One | Perfil de catálogo bloqueado | **Não suportado; sem runner completo** |
| `xenia-canary` | Xbox 360 | Jogos compatíveis, sujeito ao binário e à camada de execução | **Não suportado** para dashboard retail |
| `xbox-series` | Xbox Series S/X | Perfil de catálogo bloqueado | **Não suportado; sem runner completo** |
| `xemu` | Xbox original | Emulação do hardware; HDD/BIOS fornecidos pelo usuário | Condicional; HDD é atestado por declaração, não inspecionado automaticamente |
| `eden` | Nintendo Switch | Emulação de jogos experimental, se binário confiável existir | **Não suportado** para HOME Menu completo |
| `cemu` | Wii U | Jogos; Wii U Menu se MLC/sistema estiver configurado | Condicional |
| `dolphin` | Wii / GameCube | Jogos; Wii Menu condicionado ao NAND; IPL GameCube manual | Condicional/manual |
| `azahar` | Nintendo 3DS/2DS | Jogos; fluxo do HOME Menu manual no emulador | Manual, não automático |
| `melonds` | Nintendo DS | Jogos; menu de firmware depende da configuração | Manual/condicional |
| `mgba` | GB/GBC/GBA | Sequência de inicialização e jogos | Não existe dashboard moderno equivalente |
| `mupen64plus` | Nintendo 64 | Jogos | Não existe dashboard moderno equivalente |
| `bsnes` | Super Nintendo | Jogos | Não existe dashboard moderno equivalente |
| `mesen` | NES/sistemas clássicos | Jogos | Não existe dashboard moderno equivalente |

O catálogo não promete que cada binário está instalado. Confirme o relatório `install-report.json` gerado durante o build. Se um asset oficial não existir para Linux ou não corresponder ao padrão seguro de download, aquele perfil permanece indisponível até que exista um pacote confiável compatível. Não baixe executáveis de fontes aleatórias.

## Fontes de jogos e conteúdo autorizado

A aba **Fontes de jogos** agora inclui filtros por categoria e por cada um dos 20 perfis, usando `game-sources.json` e `platform_guidance`. Ela lista lojas oficiais (para suas versões suportadas), homebrew/demos publicados pelos autores e documentação de direitos/cópias pessoais. O catálogo explica quando uma fonte não oferece um arquivo para emulador.

**Os repositórios de emuladores normalmente distribuem código, releases e binários do emulador; não puxam jogos comerciais.** EmuStack não baixa nem instala jogos automaticamente e não lista fontes de cópias comerciais não autorizadas. Confira licença, arquivo, formato e compatibilidade item por item. Compra de uma versão PC/console não entrega automaticamente um ROM/ISO.

Fontes de descoberta incluídas: [PDRoms](https://pdroms.de/), [GameBrew](https://www.gamebrew.org/wiki/Main_Page), [itch.io homebrew](https://itch.io/games/tag-homebrew), [itch.io homebrew NES ROM](https://itch.io/games/free/tag-homebrew/tag-nes-rom), [guia oficial PPSSPP para demos/homebrew](https://www.ppsspp.org/docs/getting-started/how-to-get-demos-and-homebrew/) e [repositórios homebrew no GitHub](https://github.com/topics/homebrew-game). Essas são fontes de descoberta, não uma garantia de que cada item esteja licenciado ou seja compatível.

## Requisitos

- Linux com Docker Engine e plugin Docker Compose v2.
- Espaço em disco para imagem, cache de build e jogos/sistemas fornecidos pelo usuário.
- Para aplicações gráficas: uma sessão X11/XWayland configurável. Wayland puro, GPU NVIDIA, áudio e controles dependem da configuração de host; não são comprovados pela suíte unitária.
- Para congelar assets upstream: conectividade com os repositórios oficiais e o conjunto de ferramentas de build esperado.

## Instalar no Debian

Extraia o ZIP e entre na pasta `EmuStack-0.7.1`:

```bash
chmod +x scripts/host-setup.sh scripts/build-and-audit.sh \
  scripts/validate-project.sh scripts/runtime-acceptance.sh
./scripts/host-setup.sh
./scripts/validate-project.sh
./scripts/build-and-audit.sh
```

Depois, abra `http://127.0.0.1:8765`. O dashboard está vinculado ao loopback local, não à rede LAN. `host-setup.sh` cria as pastas por perfil e 20 tokens únicos no `.env`; não compartilhe nem versione esse arquivo. O script recusa symlinks dentro da árvore de dados dos ambientes, pois eles poderiam quebrar a separação.

Para NVIDIA, instale e teste o NVIDIA Container Toolkit no host e execute:

```bash
USE_NVIDIA=1 ./scripts/build-and-audit.sh
```

Isso apenas concede GPU aos agentes configurados. Não prova que um emulador específico, jogo, Vulkan, áudio ou sistema original funciona.

## Diagnóstico no host

```bash
python3 scripts/host-doctor.py
python3 scripts/host-doctor.py --write
```

O primeiro comando imprime o inventário disponível. `--write` salva uma fotografia em `data/host-capabilities.json`. Ela contém detalhes locais do hardware/host; revise antes de compartilhar.

## Armazenamento e snapshots por ambiente

Inicialize e inspecione a estrutura:

```bash
python3 scripts/manage-storage.py init
python3 scripts/manage-storage.py inspect
python3 scripts/manage-storage.py inspect rpcs3
```

Faça backup e restauração com o ambiente parado:

```bash
python3 scripts/manage-storage.py backup rpcs3
python3 scripts/manage-storage.py restore rpcs3 backups/rpcs3/ARQUIVO.tar.gz
```

O backup cria um arquivo TAR/GZIP com manifesto e SHA-256 dos arquivos. O restore rejeita symlinks, paths inseguros, arquivos não listados, hash incorreto e snapshot associado a outro ambiente; antes de substituir a raiz atual, mantém uma cópia de rollback. O script precisa conseguir consultar Docker para confirmar que o serviço está parado. Não use `--allow-running` a menos que aceite conscientemente o risco de snapshot inconsistente; sessões ativas podem estar alterando saves/configurações enquanto os arquivos são copiados.

Criar um disco **vazio** de dados, dentro do ambiente selecionado:

```bash
python3 scripts/manage-storage.py create-disk xemu --size 8G --format qcow2
```

É necessário instalar `qemu-utils`/`qemu-img` no host. A imagem é criada em `home/disks/` dentro do ambiente, se não houver destino alternativo permitido. Ela não tem partições ou sistema de console e não faz um dashboard aparecer.

## Sistema original do Xbox — requisito adicional de verificação

O xemu exige arquivos de sistema e uma imagem de HDD apropriados. A presença de `xemu.toml` ou de um HDD **não** prova que ele contém o dashboard Microsoft original. O EmuStack exige uma confirmação do operador vinculada ao SHA-256 da imagem:

```bash
python3 scripts/attest-xemu-dashboard.py \
  --hdd data/environments/xemu/saves/SEU-HDD-DUMP \
  --confirm-original-microsoft-dashboard
```

O caminho deve corresponder à imagem de HDD configurada no `xemu.toml`. A declaração é vinculada ao hash da imagem e fica inválida se ela mudar. Isso previne confirmação acidental da imagem errada, mas **não é detecção criptográfica nem análise interna do dashboard**; confirme manualmente a procedência e o conteúdo. Siga os documentos oficiais do [xemu](https://xemu.app/docs/required-files/) e não distribua arquivos proprietários.

## Testes e aceitação no host

`validate-project.sh` executa testes unitários/de regressão, sintaxe Python, JavaScript e shell, e a checagem do release-lock. Para validar a composição no Docker, a imagem e os serviços no seu host:

```bash
./scripts/build-and-audit.sh
./scripts/runtime-acceptance.sh
```

O acceptance espera que o dashboard e os 20 agentes estejam em execução e saudáveis. Ele verifica a topologia, os mounts, o isolamento do dashboard e o bloqueio de um boot não suportado. Também faz probes opcionais de display, áudio, Vulkan/GPU e controle. Para tornar cada requisito obrigatório, use `EMUSTACK_REQUIRE_GUI=1`, `EMUSTACK_REQUIRE_AUDIO=1`, `EMUSTACK_REQUIRE_VULKAN=1`, `EMUSTACK_REQUIRE_GPU=1` e/ou `EMUSTACK_REQUIRE_INPUT=1` antes de executar `./scripts/runtime-acceptance.sh`. A ferramenta salva um relatório sem tokens em `data/runtime-acceptance.json`. **Isso não é uma suíte de compatibilidade de jogos e não prova o boot de firmware.**

Para congelar os hashes/versões dos assets oficiais obtidos e reconstruir com o lock estrito:

```bash
FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh
```

Para também resolver pacotes Debian usando um snapshot fixo (exemplo: snapshot de 27 de outubro de 2026):

```bash
APT_SNAPSHOT_TIMESTAMP=20261027T000000Z FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh
```

A referência da imagem base é fixada pelo digest oficial no Dockerfile. O modo de snapshot pode aumentar a reprodutibilidade da resolução APT, mas congela as correções de segurança no snapshot escolhido; atualize a data após revisar os patches. O congelamento upstream só é bem-sucedido quando o build consegue baixar e validar assets oficiais. Isso ainda não promete build bit-a-bit em todas as arquiteturas/ambientes; compilações experimentais podem falhar e devem continuar explicitamente reportadas.

Diagnóstico comum:

```bash
docker compose ps
docker compose logs --tail=200 dashboard
docker compose logs --tail=200 env-rpcs3
```

## Segurança e limites

- Cada ambiente tem seus próprios `games/`, `bios/`, `saves/`, `home/` e `emulators/`. O dashboard não monta dados persistentes dos consoles nem o socket Docker.
- Os agentes ficam em bridges internas independentes e não têm egress externo por padrão. Recursos gráficos/áudio/controladores do host são montados somente pela integração opcional e aumentam a superfície de ataque.
- É isolamento por contêiner Linux, não 20 máquinas virtuais com kernels/hardware virtuais independentes. Os executáveis instalados durante o build ficam numa imagem de runtime compartilhada/imútavel; o estado persistente é isolado.
- Não há migração automática das pastas compartilhadas de versões antigas. Faça backup e mova manualmente cada arquivo para o ambiente correto.
- EmuStack não distribui ROMs, jogos, BIOS, firmware, chaves, NAND, MLC ou HDDs proprietários. Use arquivos obtidos e utilizados legalmente.
- A suíte de testes automatizada comprova lógica/estrutura, não compatibilidade upstream de cada sistema. Uma conclusão de funcionamento exige build e teste real no host.

Mais detalhes: `docs/EMULATOR_MATRIX.md`, `docs/ORIGINAL_SYSTEM_UI.md`, `docs/LOCAL_ACCEPTANCE.md`, `docs/ISOLATED_ENVIRONMENTS.md`, `docs/BUILD_REPRODUCIBILITY.md`, `docs/SECURITY.md`, `docs/TROUBLESHOOTING.md` e `docs/ROADMAP-STATUS.md` (estado das correções prioritárias), `save-paths.json` (contratos conservadores de persistência) e `scripts/audit-save-layout.py` (auditoria de saves somente de leitura).
