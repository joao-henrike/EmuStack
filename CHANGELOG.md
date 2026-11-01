# 📝 Changelog

Todas as alterações relevantes do projeto são registradas aqui. Status de compatibilidade e resultados atuais devem ser conferidos na matriz, nos artifacts e nas execuções CI; o histórico não é uma garantia de comportamento em qualquer host.

## [0.7.1] — 2026-10-28 — documentação, isolamento e rastreabilidade

- 📚 Reorganizada a documentação do projeto com uma central de navegação, guias de instalação, configuração, operação, desenvolvimento e política de atualização.
- 🧭 Ampliada a matriz de 20 perfis para separar registro, modo do release lock, disponibilidade do launcher e suporte real de boot.
- 🔐 Tornadas mais explícitas as fronteiras entre dashboard local, agente por perfil, redes, tokens, mounts e limites de contêiner.
- ✅ Expandido o checklist de aceitação para distinguir testes unitários, Compose/build, runtime acceptance, capacidades do host e teste manual de jogo/firmware.
- 🧰 Adicionados caminhos de troubleshooting para API/403, subnets, Vulkan/software rendering, áudio, controle, snapshots e assets.
- 🔄 Documentada a atualização manual do release-lock e a revisão de artifacts antes da incorporação.
- ⚖️ Reforçadas as orientações de conteúdo legal, privacidade dos relatórios e ausência de ROMs/BIOS/firmware no projeto.

### Fase 1 — Padronização Docker-first (31/10/2026)

- A decisão arquitetural é manter CMake, Clang, Qt, SDL, Node/Python de testes e emuladores no Docker. Drivers/kernel, Docker Engine/Compose e integração de hardware/sessão permanecem no host.
- `scripts/phase1.sh` passa a ser CLI canônica para `validate`, `test`, `deps`, `status` e `build` dos cinco perfis com toolchain padronizada, rede desligada nos diagnósticos e fontes somente leitura.
- `scripts/build-phase1-isolated.sh` permanece como wrapper compatível; suporte de build de bsnes incluído no Docker, deixando o host sem necessidade de toolchain para a Fase 1.
- Documento `docs/DOCKER_FIRST_ARCHITECTURE.md` registra fronteiras, dependências mínimas, privilégios, limitações e etapas de bootstrap ainda legadas.

### Fase 1 — Ambiente isolado de build para Debian 12 (31/10/2026)

- Corrigido o diagnóstico das versões: shadPS4/OpenAL usa expressão CMake 3.26 não reconhecida pelo CMake 3.25.1; KytyPS5 exige Qt6 >=6.8 e host traz 6.4.2; PPSSPP necessita SDL3 e SDL3_ttf ausentes no APT Bookworm.
- Novo preflight de versões do CMake e Qt6 no gerenciador, evitando builds demorados que inevitavelmente falhariam no host.
- Dockerfile Debian 13 Trixie de build-fonte opt-in com Qt6 6.8, SDL3, CMake mais recente. Lançador de CLI limita recursos, monta sources read-only, recusa root e deixa somente data/ gravável, sem Docker socket e sem privilegiar o dashboard.
- melonDS: Qt6 e demais pacotes instalados no host, `deps` passou sem pendências. A execução do build real está pendente.
- Compatibilidade gráfica, plugins e packaging dos binários continuam dependentes de testes em runtime.

### Fase 1 — Correções após sincronização no Debian (31/10/2026)

- 119 testes Python passaram; os 24 checkouts principais e os 14/54/28 submódulos KytyPS5/shadPS4/PPSSPP foram verificados.
- Corrigido o staging Git: prebuilds FFmpeg não devem usar o SHA do EmuStack como se fosse o SHA do submódulo. Cópias temporárias recebem HEAD/index real com alternates somente-leitura.
- Atualizada a receita PPSSPP para SDL3/SDL3_ttf, com nota sobre indisponibilidade possível dos pacotes no Debian 12.
- melonDS continua exigindo Qt6 e outras libs: `apt-get -s` somente simulou a instalação.
- Rebuild/GUI ainda pendentes para os quatro perfis; bsnes instalado com hash, mas execução gráfica não validada.

### Fase 1 — Regressões observadas no Debian (31/10/2026)

- bsnes compilado/instalado com SHA-256 registrado, mas execução gráfica ainda não testada; não mexer no binário já instalado até testar.
- KytyPS5, shadPS4 e PPSSPP bloqueados por submódulos aninhados não sincronizados. Adicionados `plan-deps` e `sync-deps` para auditar URLs/gitlinks antes de baixar commits pinados, com guardas HTTPS/host, symlink, profundidade, contagem e opt-in.
- melonDS falhou na configuração CMake por `Qt6Config.cmake` ausente. Adicionada inspeção de módulos `pkg-config` Qt6 e guia Debian para dependências Qt6.
- Nenhuma compilação pendente é declarada bem-sucedida ou funcional sem nova aceitação no host.

### Fase 1 — Integração de instalação (branch de desenvolvimento)

- Novo gerenciador de host por perfil com importação hash-verificada, backups por binário, histórico, rollback, remoção e status JSON; nenhum poder adicional para o dashboard Docker.
- Receitas de build a partir dos checkouts pinados para KytyPS5, shadPS4, PPSSPP, melonDS e bsnes, com dependências declaradas e execução opt-in. Testes de regressão cobrem SHA-256, caminhos, perfis bloqueados, instalação, remoção e rollback. Compilação real e validação de recursos auxiliares no Debian pendentes.
- Documentação [Fase 1 — Gerenciador](docs/EMULATOR_MANAGER.md), sem alteração dos 11 assets fixados/9 skip do release lock.

### Post-release hardening
- Integração inicial de todos os 18 projetos upstream via 24 submódulos Git pinados (Mupen64Plus inclui sete componentes); manifesto, gerenciador de sincronização/auditoria e fluxo de atualização revisável. Não altera o instalador de binários nem a disponibilidade de runners Xbox One/Series.
- Dashboard no longer attempts direct host-port publication from internal-only bridges. A pinned, unprivileged Nginx proxy publishes `127.0.0.1:8765` while the application remains on internal networks.
- Os diretórios temporários de client body, proxy, FastCGI, uWSGI e SCGI do Nginx usam `/tmp` (`tmpfs`), mantendo a compatibilidade com o filesystem somente leitura.
- O instalador extrai TARs com política explícita de arquivos/diretórios, sem symlinks, hardlinks ou special files; a implementação funciona no Python 3.11 e mantém testes contra path traversal.
- Probe Vulkan diferencia dispositivos físicos de fallbacks de software: `llvmpipe` adicional não invalida uma GPU física também enumerada; avisos de probe deixam de ser repetidos na saída.
- A imagem inclui `/usr/games` no `PATH`, permitindo detectar os fallbacks Debian de Dolphin e Mupen64Plus.
- Vita3K passa a usar o release oficial versionado `Vita3K-builds@4246`; o pin do DuckStation Preview foi atualizado ao SHA-256 produzido pelo download oficial no build de diagnóstico.


- Dashboard restringe requisições GET/POST operacionais por origem TCP confiável usando allowlist e IPAM previsível por perfil.
- Aceitação de runtime tenta chamadas forjadas a partir dos 20 agentes.
- Seleção de pacotes Debian usa candidato APT real; CI tenta build runtime sem downloads upstream opcionais.
- Lock estrito registra hashes SHA-256 para 11 assets oficiais, com razões explícitas para nove entradas `skip-upstream`.
- O lock documenta que cobre assets oficiais baixados; não afirma que fixa a compilação fonte de KytyPS5.
- Validação de runtime e boot real no host permanecem tarefas distintas.

### Catálogo de conteúdo autorizado

- `game-sources.json` inclui orientação por perfil, fontes de descoberta, direitos e filtros por categoria/console na UI.
- A documentação deixa explícito que repositórios de emuladores publicam código/binários, não jogos comerciais; EmuStack não baixa jogos comerciais.
- Links de descoberta não garantem a licença ou compatibilidade de cada item; a verificação é por arquivo.

## [0.7.0] — aceitação de capacidades do host

- Adicionados probes para X11/XWayland, PulseAudio/PipeWire Pulse, enumeração Vulkan, detecção de renderização software e controle explicitamente mapeado.
- Adicionados sinalizadores opt-in para tornar GUI, áudio, Vulkan, GPU e input requisitos obrigatórios da aceitação.
- Adicionada geração de relatório de aceitação sanitizado.
- Firmware/VSH do PPSSPP documentado como experimental e dependente do upstream.

## [0.6.0] — ambientes de dados privados

- Definidos 20 IDs distintos, incluindo DuckStation, PPSSPP e Vita3K.
- Xbox One e Xbox Series mantidos como perfis sem runner e bloqueados.
- Adicionada atestação manual de HDD Xbox ligada ao SHA-256 e ao ambiente.
- Adicionadas inspeção, backup/restore transacional e criação de discos de dados vazios.
- Adicionados inventário do host, digest Debian e opção de snapshot APT.
- Separação de dados, detecção de symlinks e limites de boot tornados explícitos.
