# 🎮 EmuStack

<p align="center">
  <strong>Um painel local para organizar, isolar e auditar ambientes de emulação no Linux.</strong><br>
  Um perfil por sistema · dados separados · execução verificável · sem ROMs distribuídas
</p>

<p align="center">
  <a href="https://github.com/joao-henrike/EmuStack/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/joao-henrike/EmuStack/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
  <img alt="Version 0.7.1" src="https://img.shields.io/badge/version-0.7.1-informational">
  <img alt="Linux" src="https://img.shields.io/badge/platform-Linux-lightgrey">
  <img alt="Profiles" src="https://img.shields.io/badge/profiles-20-purple">
</p>

> [!IMPORTANT]
> **20 perfis não significam 20 consoles integralmente emulados.** Um perfil listado pode não ter um binário instalável para Linux, pode depender de arquivos de sistema do usuário ou pode estar deliberadamente bloqueado. EmuStack separa perfis, dados e controle; ele não cria compatibilidade que o emulador upstream ainda não possui.

**EmuStack** é um painel de controle local com agentes isolados por perfil. O objetivo é tornar mais seguros e auditáveis a descoberta de binários, a organização de bibliotecas, a configuração, o armazenamento, os diagnósticos e a aceitação de runtime. A interface não imita o XMB, o Home Menu nem outros sistemas originais em HTML: quando há uma rota real, ela chama o emulador e depende do seu comportamento verdadeiro.

## ✨ Visão geral

| Área | O que oferece |
|---|---|
| 🧭 **Dashboard local** | Estado dos serviços, catálogo, biblioteca, sessões, logs e pré-requisitos declarados. |
| 🧱 **20 agentes de perfil** | Um serviço/controlador por ID de ambiente, com token e rede próprios. |
| 📁 **Dados separados** | Raízes exclusivas para jogos, BIOS, saves, HOME e overrides de emuladores. |
| 🛡️ **Defesas em camadas** | Rede interna por agente, mounts limitados, caminhos validados, contêiner endurecido e dashboard ligado ao loopback. |
| 🔎 **Relatórios** | Inventário do host, disponibilidade de assets e aceitação de runtime. |
| 💾 **Storage** | Inspeção, snapshots com manifesto/SHA-256, restauração com rollback e criação de discos de dados vazios. |
| 🧩 **Matriz honesta** | Separa perfil listado, asset fixado, binário disponível, suporte upstream e boot real. |
| 🧰 **Fontes de conteúdo** | Descoberta de lojas, homebrew e demos publicados pelos autores; sem downloader de jogos comerciais. |

## 🚀 Início rápido

**Plataforma de referência:** Linux x86-64, Docker Engine e plugin Docker Compose v2. Display, áudio, NVIDIA/Vulkan e controle dependem do host e são opcionais.

```bash
git clone https://github.com/joao-henrike/EmuStack.git
cd EmuStack
python3 scripts/host-doctor.py
./scripts/host-setup.sh
./scripts/validate-project.sh
./scripts/build-and-audit.sh
./scripts/runtime-acceptance.sh
```

Abra **http://127.0.0.1:8765** no navegador da própria máquina. O dashboard não foi projetado para exposição pela rede local ou pela Internet.

> [!CAUTION]
> Não publique o arquivo `.env`: ele contém tokens individuais dos agentes. Não versione nem compartilhe BIOS, firmware, chaves, NAND, MLC, HDDs, saves ou outros dados pessoais/proprietários. O projeto não inclui esses arquivos.

📘 **Primeira instalação detalhada:** [Guia de instalação](docs/INSTALLATION.md) · **Opções de configuração:** [CONFIGURATION.md](docs/CONFIGURATION.md) · **Aceitação no host:** [LOCAL_ACCEPTANCE.md](docs/LOCAL_ACCEPTANCE.md).

## 🗂️ Perfis e maturidade

A tabela abaixo é um mapa rápido, não um certificado de compatibilidade. A disponibilidade final deve ser confirmada em `install-report.json` e nos estados exibidos pelo dashboard.

| ID | Sistema | Intenção do perfil | Situação do sistema original |
|---|---|---|---|
| `kytyps5` | PlayStation 5 | Projeto experimental / compilação opcional | 🚫 Não suportado |
| `shadps4` | PlayStation 4 | Jogos compatíveis, experimentais | 🚫 Sem boot integral declarado |
| `rpcs3` | PlayStation 3 | Jogos e rota condicional VSH/XMB | 🧪 Depende de firmware e teste real |
| `duckstation` | PlayStation 1 | Jogos e rota condicional de BIOS | 🧪 Depende de BIOS e binário |
| `pcsx2` | PlayStation 2 | Jogos e Browser/Configuration do BIOS | 🧪 Condicional |
| `ppsspp` | PSP | Jogos; VSH/XMB experimental | 🧪 Experimental e dependente de firmware |
| `vita3k` | PlayStation Vita | Jogos/homebrew compatíveis | ℹ️ Interface Vita3K não é o LiveArea original |
| `xbox-one` | Xbox One | Entrada explícita no catálogo | 🚫 Bloqueado, sem runner completo |
| `xenia-canary` | Xbox 360 | Jogos conforme upstream/runner | 🚫 Dashboard retail não suportado |
| `xbox-series` | Xbox Series S/X | Entrada explícita no catálogo | 🚫 Bloqueado, sem runner completo |
| `xemu` | Xbox original | Emulação do hardware, com arquivos do usuário | 🧪 Depende de MCPX/BIOS/HDD; declaração manual não verifica conteúdo |
| `eden` | Nintendo Switch | Jogos experimentais quando há runner compatível | 🚫 HOME Menu completo não suportado |
| `cemu` | Wii U | Jogos e rota condicional para o menu | 🧪 Requer MLC/sistema válidos |
| `dolphin` | Wii / GameCube | Jogos; menu Wii condicionado a NAND | 🧪 Condicional/manual |
| `azahar` | Nintendo 3DS / 2DS | Jogos; configuração manual | 🧪 Manual |
| `melonds` | Nintendo DS | Jogos; firmware/menu condicionado à configuração | 🧪 Manual/condicional |
| `mgba` | Game Boy / Color / Advance | Jogos | ℹ️ Não há dashboard moderno equivalente |
| `mupen64plus` | Nintendo 64 | Jogos | ℹ️ Não há dashboard moderno equivalente |
| `bsnes` | Super Nintendo | Jogos | ℹ️ Não há dashboard moderno equivalente |
| `mesen` | NES e sistemas clássicos compatíveis | Jogos | ℹ️ Não há dashboard moderno equivalente |

### 🔐 O que o release lock significa

O arquivo `release-lock.json` atual é estrito e abrange os 20 IDs: **11 assets oficiais têm hash SHA-256 fixado** e **9 entradas usam `skip-upstream` com motivo declarado**. Isso fixa assets baixáveis observados no build — não significa que 20 emuladores foram instalados, que todos têm suporte Linux, nem que qualquer jogo/firmware inicializa. A compilação opcional de KytyPS5 não está coberta por esse lock. Leia [Builds e reprodutibilidade](docs/BUILD_REPRODUCIBILITY.md).

## 🧱 Arquitetura em uma olhada

```mermaid
flowchart TB
    Browser["Navegador local"]
    Dashboard["Dashboard :8765<br/>127.0.0.1 apenas"]
    Browser --> Dashboard
    Dashboard -->|"token individual + IP de gateway permitido"| A1["Agente / perfil A"]
    Dashboard -->|"token individual + IP de gateway permitido"| A2["Agente / perfil B"]
    Dashboard -->|"token individual + IP de gateway permitido"| AN["... 20 perfis"]
    A1 --- D1["games ro · bios ro<br/>saves rw · home rw"]
    A2 --- D2["games ro · bios ro<br/>saves rw · home rw"]
    AN --- DN["dados próprios"]
    A1 -. "rede interna exclusiva" .- N1["net A"]
    A2 -. "rede interna exclusiva" .- N2["net B"]
    AN -. "rede interna exclusiva" .- NN["net N"]
```

Cada agente compartilha o kernel Linux do host e a imagem de programas do runtime; **não** é uma VM independente. O dashboard é um orquestrador privilegiado, não deve ser exposto remotamente. Leia o [modelo de segurança](docs/SECURITY.md) e a [arquitetura detalhada](docs/ARCHITECTURE-AND-TESTS.md).

## 📚 Documentação completa

| Guia | Para que serve |
|---|---|
| 🧭 [Índice da documentação](docs/INDEX.md) | Navegação por objetivo, do primeiro uso à engenharia. |
| 🛠️ [Instalação](docs/INSTALLATION.md) | Pré-requisitos, setup, build, gráficos, áudio e controle. |
| ⚙️ [Configuração](docs/CONFIGURATION.md) | Variáveis, limites de recursos, modos de build e sinalizadores de aceitação. |
| 🎮 [Guia do usuário](docs/USER_GUIDE.md) | Painel, biblioteca, jogos, sistemas originais e sessões. |
| 🧩 [Matriz de emuladores](docs/EMULATOR_MATRIX.md) | 20 perfis, limites e estados de confiança. |
| 🧱 [Arquitetura e testes](docs/ARCHITECTURE-AND-TESTS.md) | Componentes, fluxos, verificações e limites dos testes. |
| 🔒 [Ambientes isolados](docs/ISOLATED_ENVIRONMENTS.md) | Rede, mounts, tokens, diretórios e contenção. |
| 🛡️ [Segurança](docs/SECURITY.md) | Modelo de ameaça, defaults, riscos e práticas seguras. |
| ✅ [Aceitação local](docs/LOCAL_ACCEPTANCE.md) | Testes no host e critérios para aprovação. |
| 🖥️ [Menus originais](docs/ORIGINAL_SYSTEM_UI.md) | Pré-requisitos e limites do boot de sistema/menu real. |
| 📦 [Build e reprodutibilidade](docs/BUILD_REPRODUCIBILITY.md) | Imagem base, APT, release lock e atualização de hashes. |
| 🔄 [Releases e atualizações](docs/RELEASE_AND_UPDATES.md) | Atualizar assets com revisão e rastreabilidade. |
| 🕹️ [Fontes de jogos](docs/GAME_SOURCES.md) | Lojas, homebrew, demos e orientação de direitos. |
| 🧰 [Solução de problemas](docs/TROUBLESHOOTING.md) | Diagnóstico por sintoma. |
| 🔌 [Referência de API e CLI](docs/API_REFERENCE.md) | Endpoints internos, payloads, autenticação e comandos. |
| 🧑‍💻 [Desenvolvimento](docs/DEVELOPMENT.md) | Contribuir, validar e manter a integridade dos manifestos. |
| 📝 [Changelog](CHANGELOG.md) | Histórico das mudanças. |

## ✅ Validação: o que cada camada prova

| Camada | Evidência que pode fornecer | O que não prova |
|---|---|---|
| Testes de unidade | Lógica, validações e regressões cobertas pelos testes | Compose real, drivers, GUI ou boot de jogo |
| CI/Compose | Parsing de manifests, build da imagem no runner e probes automatizados executados | GPU física, desktop, áudio, controle físico ou desempenho no seu host |
| Runtime acceptance no host | Serviços, topologia, mounts, controle do dashboard e capacidades opcionais detectáveis | Compatibilidade de todos os títulos ou autenticidade de todos os arquivos de sistema |
| Teste manual por perfil | Evidência direta para a máquina, binário, arquivos e jogo testados | Compatibilidade universal em outros hosts e versões |

O pipeline e os resultados recentes ficam em [GitHub Actions](https://github.com/joao-henrike/EmuStack/actions). Confira o estado do commit que pretende usar; badges e relatórios são dinâmicos.

## ⚖️ Conteúdo, direitos e licenças

- EmuStack não instala nem distribui ROMs, BIOS, firmware, chaves, NAND, MLC, discos de sistema ou jogos comerciais.
- A lista de fontes é um índice de descoberta; ela não garante a licença, formato ou compatibilidade de cada item.
- Obter um jogo numa loja não significa que a loja forneça uma ROM/ISO utilizável por um emulador.
- A licença MIT deste repositório cobre as integrações de EmuStack; cada emulador e dependência mantém sua própria licença.

## 🤝 Contribuições

Leia [Desenvolvimento](docs/DEVELOPMENT.md), faça mudanças em uma branch, execute `./scripts/validate-project.sh` e abra um Pull Request. Melhorias na documentação são bem-vindas, especialmente quando separam comportamento observado de expectativa.

---

<p align="center"><sub>EmuStack · documentação orientada à evidência · não distribui conteúdo de console protegido</sub></p>
