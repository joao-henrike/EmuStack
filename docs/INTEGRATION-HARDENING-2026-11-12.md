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
