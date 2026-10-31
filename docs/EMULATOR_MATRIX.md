# 🧩 Matriz de emuladores, perfis e sistemas originais

Esta matriz separa cinco perguntas: **o perfil está cadastrado? O asset upstream está fixado? O binário foi instalado nesta build? Há suporte upstream para o alvo? O sistema/menu realmente inicializou?** As respostas não são intercambiáveis.

## 📌 Estados do release lock

No `release-lock.json` estrito atual: 20 IDs são representados; 11 usam um asset oficial com hash SHA-256 (`pinned` ou `pinned-url`) e 9 estão explicitamente em `skip-upstream`. O modo lock não é classificação de maturidade nem garantia de execução. O relatório de build (`install-report.json`) é que deve ser usado para inspecionar o que ocorreu naquele build.

| Perfil | Console | Lock atual | Intenção e limite explícito |
|---|---|---|---|
| `kytyps5` | PS5 | `skip-upstream` | Projeto experimental. O build fonte opcional não está pinado pelo lock atual; boot integral não suportado. |
| `shadps4` | PS4 | `skip-upstream` | Execução de jogos depende da maturidade upstream e do binário; sem boot integral declarado. |
| `rpcs3` | PS3 | `pinned` | Emulação de jogos conforme upstream; VSH/XMB condicional ao firmware e a teste no host. |
| `duckstation` | PS1 | `pinned` | AppImage do canal Preview pinado por SHA-256; o tag é móvel, portanto uma troca upstream exige revisão do hash. Jogos e rota BIOS continuam condicionais. |
| `pcsx2` | PS2 | `pinned` | Jogos e Browser/System Configuration condicionados à BIOS/configuração. |
| `ppsspp` | PSP | `skip-upstream` | Runner não instalado pelo asset fixado no lock atual; VSH/XMB é exploratório e exige firmware. |
| `vita3k` | PS Vita | `pinned` | Build oficial versionado `4246` (`Vita3K-builds`) com SHA-256 fixado; jogos/homebrew compatíveis seguem sujeitos a limitações do upstream. A UI não é LiveArea original. |
| `xbox-one` | Xbox One | `skip-upstream` | Placeholder de catálogo, bloqueado intencionalmente; sem runner integral. |
| `xenia-canary` | Xbox 360 | `pinned` | Asset oficial pinado é ZIP Windows; execução Linux pode depender de Wine e requer verificação no host. Dashboard retail não suportado. |
| `xbox-series` | Xbox Series S/X | `skip-upstream` | Placeholder de catálogo, bloqueado intencionalmente; sem runner integral. |
| `xemu` | Xbox original | `pinned` | Hardware emulado conforme xemu; MCPX/BIOS/HDD do usuário e teste real são necessários. |
| `eden` | Nintendo Switch | `pinned-url` | Asset por URL oficial/hash fixado; emulação experimental. HOME Menu integral não suportado pelo perfil atual. |
| `cemu` | Wii U | `pinned` | Jogos; Wii U Menu condicionado a MLC/sistema compatíveis. |
| `dolphin` | Wii/GameCube | `skip-upstream` | AppImage upstream não pinado; Debian Trixie fornece `dolphin-emu` como fallback APT. O menu Wii depende de NAND e configuração. |
| `azahar` | Nintendo 3DS/2DS | `pinned` | Jogos compatíveis; acesso ao HOME Menu é manual e depende da configuração. |
| `melonds` | Nintendo DS | `skip-upstream` | Asset upstream não instalado pelo lock atual; opções de firmware/menu são condicionais. |
| `mgba` | Game Boy/Game Boy Color/Game Boy Advance | `pinned` | Jogos; não há dashboard moderno equivalente. |
| `mupen64plus` | Nintendo 64 | `skip-upstream` | Sem asset upstream pinado; Debian Trixie fornece `mupen64plus-ui-console` e plugins como fallback APT. Experiência centrada em jogos. |
| `bsnes` | Super Nintendo | `skip-upstream` | Asset upstream não instalado pelo lock atual; experiência centrada em jogos. |
| `mesen` | NES/clássicos suportados | `pinned` | Jogos; não há dashboard moderno equivalente. |

## 🖥️ Rotas declaradas para menus/sistemas originais

| Plataforma | Rota | Pré-requisitos e ressalvas |
|---|---|---|
| PS1 / DuckStation | Shell/BIOS via argumento do emulador | BIOS válido detectado; requer janela e teste real. |
| PS2 / PCSX2 | Browser/System Configuration do BIOS | Dump válido e seleção/configuração correta na interface. |
| PS3 / RPCS3 | VSH/XMB | Firmware instalado e módulo VSH encontrado; não basta o executável existir. |
| PSP / PPSSPP | VSH/XMB via `--vsh` em versão compatível | Experimental; exige firmware `flash0` e a versão precisa reconhecer o argumento. |
| Xbox original / xemu | Boot de HDD do usuário | MCPX/BIOS/HDD configurados. A atestação do HDD é uma declaração por hash, não inspeção interna. |
| Wii / Dolphin | Wii System Menu | NAND com System Menu instalado e teste real. |
| Wii U / Cemu | Wii U Menu | MLC e `men.rpx` válidos. |
| Azahar / melonDS | Fluxos manuais | Abrir e configurar no emulador; não há uma promessa de boot automático pelo painel. |
| PS4 / PS5 / Switch / Xbox 360 retail dashboard / Xbox One / Xbox Series | Não declarado como boot integral nesta versão | Não imitar a interface em HTML nem remover o bloqueio para parecer funcional. |
| GB/NES/SNES/N64 e similares | Sequência própria da geração | Não existe necessariamente dashboard comparável aos consoles modernos. |

## 🧪 Como provar uma afirmação de compatibilidade

Para registrar um resultado reproduzível, anote:

- ID do ambiente e host/sistema operacional/arquitetura.
- Commit do EmuStack, hash do `release-lock.json` e versão/hash do binário instalado.
- Renderer detectado (hardware/software), driver, configuração de display e áudio.
- Fonte e versão do jogo/homebrew autorizado e hash do arquivo quando apropriado.
- Pré-requisitos de firmware/BIOS presentes, sem publicar o conteúdo proprietário.
- Resultado: inicializa, chega ao menu, chega ao jogo, renderiza, tem áudio/entrada, persiste save e encerra corretamente.
- Logs/relatório sanitizados e limitações observadas.

**Nunca extrapole um teste de um título/host para todos os jogos ou computadores.** A aceitação de runtime prova estrutura/API e probes selecionados, não compatibilidade por console.

## 🔒 Infraestrutura compartilhada e isolamento

A imagem de programas do runtime é comum; cada agente tem seu próprio HOME, saves e bibliotecas. GPU, display e áudio são recursos do host e podem ser compartilhados apenas por configuração explícita. Isso não transforma os agentes em VMs completas. Veja [Ambientes isolados](ISOLATED_ENVIRONMENTS.md) e [Segurança](SECURITY.md).
