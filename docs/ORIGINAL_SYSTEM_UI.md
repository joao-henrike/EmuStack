# Sistemas originais e menus reais

O EmuStack não recria o XMB, o Home Menu nem outros dashboards em HTML. Quando existe suporte real, ele invoca o emulador com os arquivos de sistema do usuário e a tela original vem desse código emulado. Quando não existe caminho comprovado, o perfil permanece manual/indisponível/não suportado.

## Onde ficam os arquivos

Todos os caminhos são relativos à raiz de **um único ambiente**:

```text
data/environments/<id>/bios/    # BIOS/boot ROMs autorizados (montagem read-only)
data/environments/<id>/home/    # HOME persistente: firmware instalado, NAND/MLC/HDD e configs, quando aplicável
data/environments/<id>/saves/   # espaço persistente para saves quando suportado
```

Não use uma pasta global para compartilhar BIOS, NAND, MLC, HDD, saves ou configurações entre ambientes. O HOME isolado de cada agente é `/home/emu` dentro do contêiner.

## Caminhos integrados e limites

### PlayStation 3 — RPCS3 / VSH-XMB

A estratégia procura o módulo VSH instalado pelo RPCS3 em pastas de configuração dentro do HOME daquele agente. Instale firmware do PS3 usando o fluxo/documentação oficial do RPCS3 e confira o estado do perfil. O caminho precisa ainda ser testado com a versão de emulador/build que foi instalada.

### PlayStation 2 — PCSX2 / BIOS-Browser

O perfil procura BIOS `.bin` em `data/environments/pcsx2/bios/pcsx2/` e nas pastas de BIOS do PCSX2 dentro de `data/environments/pcsx2/home/`. Confirme a seleção de BIOS na interface do PCSX2. O boot não é ativado só pela existência de um arquivo de nome arbitrário; deve existir um dump válido e permitido.

### Xbox original — xemu

A configuração é por ambiente em `data/environments/xemu/home/.config/xemu/xemu.toml`. A presença do TOML não prova que o HDD contenha o dashboard original Microsoft; uma imagem de demonstração pode conter um dashboard aberto alternativo. O boot é bloqueado até que o caminho do HDD configurado exista, seja validado e receba uma atestação explícita do operador ligada ao SHA-256. Gere-a com `scripts/attest-xemu-dashboard.py --hdd <caminho> --confirm-original-microsoft-dashboard` somente depois de verificar manualmente o dump. Isso é uma declaração auditável, não reconhecimento automático de conteúdo. O EmuStack ainda não consegue verificar por conta própria se o HDD contém o dashboard retail original.

### Nintendo Wii — Dolphin

O perfil procura o Wii System Menu instalado no NAND do Dolphin em `data/environments/dolphin/home/.local/share/dolphin-emu/Wii/` (ou os diretórios alternativos reconhecidos). Instale apenas arquivos de sistema que você pode legalmente utilizar. A detecção de pastas não prova que todos os menus/jogos funcionem corretamente.

### Nintendo Wii U — Cemu

A MLC isolada fica por padrão em `data/environments/cemu/home/.local/share/Cemu/mlc01/`. O menu requer arquivos de sistema próprios e um `men.rpx` compatível; a simples pasta MLC não basta.

### Outras gerações

Azahar e melonDS têm fluxos manuais de sistema/firmware; GBA/N64/SNES/NES usam sequências de inicialização apropriadas à geração, e não um dashboard comparável ao de consoles modernos. PS4, PS5, Switch, Xbox 360 e Xbox One não estão declarados como boot integral de sistema nesta versão.

## Como conferir

Abra **Sistemas originais**, escolha o perfil e leia estado, checks e passos de configuração. Se o status não permitir boot, a rota de API rejeita o pedido; não há fallback para uma tela HTML falsa. Para cada mudança de firmware, configuração ou versão do emulador, valide primeiro o log daquele ambiente.

## Referências upstream de linha de comando

Essas páginas/fonte são usadas para conferir a sintaxe dos argumentos integrados; elas **não** provam que um firmware, menu ou jogo inicializará nesta imagem e GPU:

- PCSX2 — [opções oficiais de linha de comando](https://pcsx2.net/docs/advanced/cli/) (`-bios`, `-fullscreen`).
- Dolphin — [referência de uso no repositório oficial](https://github.com/dolphin-emu/dolphin/blob/master/Readme.md?plain=1) (`-n` / `--nand_title`).
- Cemu — [opções oficiais implementadas na linha de comando](https://github.com/cemu-project/Cemu/blob/main/src/config/LaunchSettings.cpp) (`--mlc`, `--game`, `--fullscreen`).
- xemu — [argumentos oficiais](https://xemu.app/docs/cli/) (`-full-screen`, `-config_path`).
- RPCS3 — [implementação de BootVSH no projeto](https://github.com/RPCS3/rpcs3/blob/master/rpcs3/rpcs3qt/main_window.cpp); o boot integrado do EmuStack ainda depende de testar a versão do binário instalado.


### PlayStation Portable (PSP)

O EmuStack 0.7.1 inclui uma rota experimental para o VSH/XMB do PSP via `PPSSPP --vsh --fullscreen`. O caminho upstream depende de um dump real de firmware em `assets/flash0/` e é explicitamente exploratório, não uma função estável garantida. No ambiente isolado, o caminho host é `data/environments/ppsspp/bios/flash0/`, montado como `/opt/emustack/assets/flash0/` somente leitura.

A rota só é apresentada como disponível quando os arquivos `vsh/module/vshmain.prx` e `kd/pspbtcnf.bin` foram encontrados sem symlinks. Isso verifica pré-requisitos, não o sucesso visual do boot. A instalação do PPSSPP precisa reconhecer `--vsh`. Referências oficiais: [CLI do PPSSPP](https://www.ppsspp.org/docs/reference/command-line/) e [investigação upstream do VSH](https://github.com/hrydgard/ppsspp/blob/master/docs/VSHBootInvestigation.md).

## Semântica dos estados e evidências de boot

A API dos perfis distingue explicitamente a disponibilidade para tentar iniciar de uma inicialização comprovada:

- `prerequisites_detected`: os arquivos/configurações esperados foram encontrados; isto **não** confirma integridade do firmware nem boot bem-sucedido.
- `can_attempt_boot`: os pré-requisitos/configurações permitem solicitar uma tentativa de boot pelo caminho implementado; não é uma garantia de compatibilidade.
- `boot_observed`: existe uma observação de runtime registrada de que o boot ocorreu. Não deve ser inferida apenas da presença de um executável ou arquivo de sistema.
- `smoke_test_passed`: um teste mínimo definido para o perfil passou; deve ter evidência reproduzível.
- `boot_validation_status`: resumo da etapa de validação (`not-ready`, `prerequisites-detected`, `attempt-available-not-tested`, `boot-observed` ou `smoke-test-passed`).

O campo legado `can_boot_original` permanece por compatibilidade com clientes antigos; o seu significado histórico é “a tentativa está habilitada”, e **não** “o boot foi comprovado”. O CLI, o agente isolado e o dashboard devem preferir `can_attempt_boot`. Até que um teste de runtime real grave evidência, a interface precisa continuar exibindo o boot como não verificado.

Esses estados também não equivalem à compatibilidade de jogos. O sucesso de inicialização do menu, quando comprovado, é uma etapa separada de qualquer teste de jogo ou gameplay.
