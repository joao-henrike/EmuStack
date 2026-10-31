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

### Post-release hardening
- Dashboard no longer attempts direct host-port publication from internal-only bridges. A pinned, unprivileged Nginx proxy publishes `127.0.0.1:8765` while the application remains on internal networks.
- Os diretórios temporários de client body, proxy, FastCGI, uWSGI e SCGI do Nginx usam `/tmp` (`tmpfs`), mantendo a compatibilidade com o filesystem somente leitura.
- Probe Vulkan diferencia dispositivos físicos de fallbacks de software: `llvmpipe` adicional não invalida uma GPU física também enumerada; avisos de probe deixam de ser repetidos na saída.


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
