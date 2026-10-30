# EmuStack 0.7.1 — Relatório de arquitetura, alterações e testes

> **EMUSTACK // GAMING LAB** · [README](../README.md) · [Instalação](INSTALLATION.md) · [Guia do usuário](USER_GUIDE.md) · [Matriz de emuladores](EMULATOR_MATRIX.md) · [Segurança](SECURITY.md) · [Identidade visual](IDENTIDADE-VISUAL.md)

**Data:** 29 de outubro de 2026  
**Última validação remota confirmada na revisão:** o workflow GitHub Actions `EmuStack CI` passou no commit `f3b28fa435a5083def049f389cb8016c961b86ea` (run [#35](https://github.com/joao-henrike/EmuStack/actions/runs/40886953420)). Essa execução reportou 79 testes Python aprovados, lock estrito, validação de Compose, build e runtime acceptance. O build usou `INSTALL_UPSTREAM=0` e `BUILD_KYTYPS5=0`: portanto, não comprovou downloads/builds upstream nem suporte a KytyPS5. O runner reportou `llvmpipe`, logo não comprova aceleração por GPU física. CI verde não certifica todos os jogos, firmwares ou hosts.

## Resumo

EmuStack 0.7.1 entrega 20 perfis de runtime isolados e 21 entradas de sistema/menu documentadas. A versão melhora a separação das pastas, a prevenção de symlinks em raízes de ambiente, o armazenamento, o diagnóstico do host, a declaração de capacidade, a rastreabilidade de releases e a validação do runtime.

Isto não equivale a 20 consoles integralmente emulados. O dashboard é um plano de controle; os sistemas originais só podem iniciar se o emulador upstream suportar esse caminho e os arquivos válidos do usuário estiverem configurados. Sistemas sem esse suporte permanecem explicitamente não suportados.

## Alterações implementadas

### Ambientes e isolamento

- O dashboard aplica uma allowlist de IPs TCP de origem para POSTs mutáveis. Cada rede usa IPAM estático (`gateway .1`, agente `.2`, dashboard `.3`) para impedir que cabeçalhos HTTP forjados por um agente autorizem uma chamada ao dashboard.
- O runtime acceptance verifica a fronteira de origem e tenta requisições forjadas a partir dos agentes. O workflow CI do GitHub passou por essa etapa no run [40886953420](https://github.com/joao-henrike/EmuStack/actions/runs/40886953420); isso comprova a topologia/testes daquela execução de CI, não uma prova universal contra todo ataque ou configuração de host.

- 20 IDs correspondem exatamente entre `catalog.json` e `environments.json`.
- Cada agente tem diretórios próprios `games/`, `bios/`, `saves/`, `home/` e `emulators/`.
- Cada agente recebe uma bridge interna exclusiva; o dashboard se conecta aos agentes para orquestrá-los.
- O dashboard não monta as pastas persistentes dos ambientes nem o socket Docker.
- Os ambientes usam root filesystem read-only, `cap_drop: ALL`, `no-new-privileges`, limites configuráveis de CPU/RAM/PIDs e tokens individuais.
- O setup e a ferramenta de armazenamento recusam raízes/paths de mount que sejam symlinks de forma a redirecionar um ambiente para outro.

### Perfis e capacidade de boot

- Perfis antigos redundantes ou não executáveis foram removidos: `sharpemu`, `ps5pcem`, `windurango`, `xwine1` e `xenia-edge`.
- Adicionados perfis para DuckStation/PS1, PPSSPP/PSP e Vita3K/PS Vita.
- Xbox One e Xbox Series são placeholders bloqueados, sem comando de lançamento; não foi criada interface falsa ou executável fictício.
- PS1, PS2, PS3, Wii e Wii U têm rotas condicionais de BIOS/menu. O PSP ganhou rota VSH/XMB com `PPSSPP --vsh`, explicitamente experimental e dependente de firmware e versão compatível.
- O Xbox original requer configuração do xemu e uma confirmação explícita da imagem HDD ligada ao SHA-256 e ao caminho montado. Essa confirmação é uma declaração do operador e **não** prova automaticamente o conteúdo interno do HDD.
- PS4/PS5, Xbox 360 dashboard, Xbox One/Series e Nintendo Switch HOME Menu não são apresentados como boot integral de sistema original.

### Armazenamento e diagnóstico

- `scripts/manage-storage.py`: `init`, `inspect`, `backup`, `restore`, `create-disk`.
- Snapshots contêm manifesto, hashes SHA-256, limites de tamanho/quantidade e validação de paths. Restore verifica a identidade do ambiente, rejeita links/especiais e conserva o estado anterior para rollback.
- A criação `qcow2`/`raw` gera somente disco de dados vazio; não instala OS, BIOS, jogos ou dashboard.
- `scripts/host-doctor.py` faz diagnóstico de Docker/Compose, memória, GPU NVIDIA, Vulkan, display, áudio, controles e `qemu-img`.
- `scripts/runtime-acceptance.py` verifica serviços, saúde, redes, mounts, flags de hardening, bloqueio de boot não suportado e probes opcionais de X11/XWayland, áudio Pulse, Vulkan/GPU real versus renderer de software e dispositivo de controle explicitamente mapeado. Grava um relatório sem tokens em `data/runtime-acceptance.json`.

### Reprodutibilidade

- O Dockerfile usa o digest multi-arquitetura da imagem oficial Debian `trixie-slim` observado em 28-10-2026: `sha256:89c1ea91e897f0fe0a3731595330bc45b8bdef4047464a07116f891a94054b31`. Referência oficial: https://hub.docker.com/_/debian/tags/ .
- O build do KytyPS5 está restrito a uma tag e checa um prefixo de commit esperado.
- `APT_SNAPSHOT_TIMESTAMP=YYYYMMDDTHHMMSSZ` permite resolver pacotes usando um snapshot Debian datado. Isso congela também as correções de segurança do snapshot, por isso deve ser atualizado após revisão de patches.
- `FREEZE_RELEASE_LOCK=1` tenta capturar hashes dos assets oficiais realmente obtidos e reconstruir com um lock estrito.
- O `release-lock.json` atual está em modo estrito: os assets oficiais pináveis possuem hashes SHA-256 e as entradas não instaladas ficam marcadas como `skip-upstream` com justificativa. Isso torna explícitas as limitações: projetos sem runner ou asset confiável/disponível não são instalados nem tratados como presentes. O lock não congela por si só as versões dos pacotes APT; para isso, é preciso configurar `APT_SNAPSHOT_TIMESTAMP`.
- Não há garantia de build bit-a-bit idêntico em toda arquitetura ou versão de Docker/BuildKit. Releases experimentais, pacotes APT indisponíveis e builds upstream podem falhar; o relatório de instalação deve ser consultado.

## Resultados de validação executada

| Verificação | Resultado |
|---|---:|
| Testes unitários/regressão Python | **79/79 passaram** |
| Casos de recomendação de lançamento JavaScript | **13/13 passaram** |
| Verificações estáticas da UI de sistemas originais | **11 assertions passaram** |
| Compilação sintática Python | Passou |
| Sintaxe shell dos scripts | Passou |
| Parse YAML do `compose.yaml` | Passou; 22 serviços definidos |
| Parse YAML do `compose.nvidia.yaml` | Passou; 20 overlays de agente |
| Helpers de acceptance/probes | Passou; cenários simulados de integração disponível/ausente |
| IDs catálogo ↔ ambientes | 20/20 iguais e únicos |
| Alvos de sistema/menu documentados | 21 |
| Referências aos antigos perfis duplicados no catálogo/documentação | Nenhuma |

## Não executado / limitações externas

O container de auditoria usado para inspeção local não contém `docker`, `podman` nem `buildah`, então não pôde executar o runtime localmente. Isso foi coberto, para a versão commitada no GitHub, pelo workflow CI remoto: no run [40886953420](https://github.com/joao-henrike/EmuStack/actions/runs/40886953420), o build Docker, a inicialização dos agentes/dashboard e o `scripts/runtime-acceptance.sh` concluíram com sucesso. O workflow constrói sem downloads opcionais de upstream, portanto não prova que todos os binários comerciais/experimentais estejam instalados; confira o `release-lock.json` e o relatório de instalação. Ainda são necessários testes de compatibilidade por jogo e de boot real de firmware/menu no hardware-alvo.

Também não foi possível provar a execução com sua GPU, áudio, controle, jogos, firmware, NAND/MLC/HDD ou interfaces originais no seu computador. São necessários testes no Debian host com Docker Engine + Compose v2 e arquivos próprios legalmente utilizáveis.

## Próximos comandos no Debian do usuário

```bash
chmod +x scripts/host-setup.sh scripts/build-and-audit.sh scripts/validate-project.sh scripts/runtime-acceptance.sh
./scripts/host-setup.sh
./scripts/validate-project.sh
./scripts/build-and-audit.sh
./scripts/runtime-acceptance.sh
```

Para tentar congelar hashes de releases com build online:

```bash
FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh
```

Modo APT com snapshot fixo (a data de exemplo precisa ser atualizada após revisão das atualizações de segurança):

```bash
APT_SNAPSHOT_TIMESTAMP=20261027T000000Z FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh
```

O aceite de runtime verifica topologia Docker, endpoints e, quando configurados, conectividade básica de display/áudio/Vulkan/controle. Não verifica entradas físicas do controle nem compatibilidade universal de jogos; o boot real de cada sistema ainda exige teste individual por perfil.

## Evidência de validação por execução

O bloco de resultado fixo acima registra a última execução de referência de `main` observada durante esta revisão; ele não é um atestado perpétuo do estado de todo branch. Para evitar que novos resultados fiquem presos a um SHA antigo, cada execução de `EmuStack CI` gera agora um resumo no **GitHub Actions Step Summary** e publica o artefato `emustack-validation-report-<run_number>` com o commit, o resultado do job e os limites explícitos da validação. Ao revisar uma mudança, use o artefato da execução ligada ao commit/PR em questão, junto dos logs de cada etapa.

A CI mantém downloads upstream e o build experimental de KytyPS5 desligados, e roda em runner hospedado. Portanto, o relatório distingue a validação de código, manifestos, Compose e runtime isolado de qualquer teste em GPU física, firmware próprio, boot de console ou compatibilidade de jogos. Um relatório verde não amplia esse escopo.

## Validação cruzada de manifestos

A validação local/CI inclui agora `scripts/validate-manifests.py`, executado por `scripts/validate-project.sh`. Ele cruza os contratos de `catalog.json`, `environments.json`, `console-systems.json`, `game-sources.json`, `release-lock.json`, `compose.yaml` e `compose.nvidia.yaml`.

A verificação valida IDs únicos e referências, versão de schema por manifesto (incluindo `game-sources.json` v2), caminhos relativos por ambiente, estratégias de boot permitidas, categorias/URLs das fontes, cobertura do lock estrito, serviços de agentes, mounts e modos esperados, redes internas/IPs estáticos e allowlist de origem do dashboard. O validador tem testes negativos para IDs duplicados e referências de ambiente quebradas.

Execute em uma cópia do projeto com Python e PyYAML instalados:

```bash
python3 scripts/validate-manifests.py
python3 -m unittest discover -s tests -v
bash scripts/validate-project.sh
```

Esta validação prova consistência estrutural dos manifestos e do YAML; não testa downloads de upstream, executabilidade real dos emuladores, BIOS, boots de console, compatibilidade de jogos nem aceleração por GPU física.
