# EmuStack — integração de hardening (12/11/2026)

Esta branch parte de `fix/dashboard-degraded-startup` (PR #7) e incorpora melhorias independentes de `fix/roadmap-p0-p1` (PR #6), preservando o proxy local, o isolamento de agentes e o gerenciador Docker-first.

## O que foi aplicado

- Removidas as concessões NVIDIA para os perfis sem runner Xbox One e Xbox Series.
- Adicionado inventário conservador de caminhos de saves (`save-paths.json`) com auditoria somente leitura; não move nem liga arquivos automaticamente.
- Adicionado validador cruzado de catálogo, ambientes, sistemas, fontes, locks, saves, Compose, topologia do proxy e rede de cada agente.
- Integrado à validação geral e coberto por testes de regressão para manifestos, caminhos e cadeia de suprimentos.
- Adicionados Syft e Trivy com versões e SHA-256 fixos, geração de SBOM SPDX, relatório de vulnerabilidades HIGH/CRITICAL e artefatos da execução CI. Os achados de vulnerabilidade são report-only; erros de integridade das ferramentas e execução continuam bloqueantes.
- Corrigidas métricas de processos por modo (agentes Docker vs. processos locais) com regressões específicas.
- Adicionados estados separados de pré-requisitos, tentativa de boot, boot observado e smoke test, sem declarar menu de console inicializado automaticamente.
- Integrada restauração de snapshots mais rigorosa com testes de casos corrompidos/adulterados.
- A CI preserva os testes de runtime/isolamento da PR #7 e produz relatório por commit.

## Critérios de aceite

1. CI da branch com Python/Node, manifesto/locks, Compose, build e runtime acceptance verde.
2. SBOM e JSON Trivy anexados à CI, com os achados revisados.
3. Execução no Debian do `bash scripts/phase1.sh validate`, compilação dos cinco perfis e `bash scripts/phase1-acceptance.sh`.
4. GUI, GPU/Vulkan, áudio, gamepad e save/load validados por perfil com conteúdo autorizado.
5. Revisão do trabalho ainda exclusivo da PR #6: instalador, guardrails e demais melhorias não integradas. **Esta integração não equivale a merge completo da PR #6.**

Não declarar emuladores operacionais ou mergear em `main` com base somente em testes estáticos.


## Correção adicional — bootstrap APT (14/11/2026)

- Exigência de APT 3.0.4+ antes da instalação de dependências, corrigindo CVE-2026-109518 no Debian Trixie.
- Primeira atualização de índices e instalação do APT corrigido usam `Acquire::Retries=0`, reduzindo a exposição do APT vulnerável antes da atualização.
- Atualização de pacotes instalados antes de adicionar dependências de runtime; snapshots antigos falham fechados.
- Relatório Trivy agora diferencia contagem de achados por pacote e CVEs únicos para evitar inflar a interpretação do inventário.


## SBOM — rastreamento de dependências

O relatório Trivy agora apresenta, por achado, a cadeia SPDX de dependência desde o pacote raiz até o pacote vulnerável. A triagem de 14/11 identificou que GDCM/MariaDB chegam pelo stack APT do Mupen64Plus e libstb pelo Dolphin. A separação de imagens por perfil foi registrada como próxima mudança arquitetural, sem remover funcionalidades antes da validação de overlays e dos scans por imagem.


## Imagens dedicadas por perfil

- O alvo `runtime` é usado pelo dashboard, CLI e 18 agentes. Dolphin e Mupen64Plus recebem, respectivamente, `runtime-dolphin` e `runtime-mupen64plus`, com tags próprias.
- Removidas do APT comum as dependências explícitas desses dois perfis. O instalador não coloca o AppImage Dolphin na imagem comum; o download oficial permanece disponível apenas no target Dolphin.
- Registros de instalação por perfil atualizam o relatório herdado, sem apagar os estados de outros ambientes.
- Adicionadas verificações de executáveis ausentes/presentes, três IDs Docker distintos e CI que constrói as três imagens.
- Syft + Trivy são executados individualmente; o artefato inclui matriz de CVEs novos por perfil, com contagens por pacote e CVEs únicos.
- Pendente: revisar os resultados específicos, corrigir vulnerabilidades aplicáveis e validar GPU, áudio, controle e execução gráfica no host Debian.

## Regressão de fronteira APT e matriz de CVEs

Além das verificações de binários presentes/ausentes, a CI confere diretamente o banco `dpkg` das três imagens. O runtime comum não pode conter `dolphin-emu`, `mupen64plus-ui-console`, `libgdcm3.0t64`, `libmariadb3` ou `libstb0t64`. As imagens específicas devem conter suas dependências e não as da outra. A matriz da CI #248 apresenta 459, 475 e 545 componentes SPDX nas imagens comum, Dolphin e Mupen64Plus, respectivamente; essa contagem é contextual e não um teto fixo para builds futuros.

## Gate CI para novos CRITICAL (14/11/2026)

Adicionados `security-critical-baseline.json`, `scripts/check-critical-cves.py` e testes de regressão. Um novo CVE/GHSA CRITICAL em qualquer uma das três imagens bloqueia a CI e aparece no artefato. Os CVEs já existentes permanecem explicitamente não resolvidos; o gate não os oculta, não aprova release e não declara impacto ou exploração. A política exige três imagens, IDs únicos, correspondência de tags e contagens consistentes. Sem patchear upstream indevidamente, priorizar atualização oficial Debian e testes físicos antes de merge.
