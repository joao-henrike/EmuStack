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
