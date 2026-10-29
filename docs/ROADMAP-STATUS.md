# EmuStack — status da execução do roteiro

Este documento acompanha a execução incremental das correções prioritárias. O estado de integração da versão atual deve ser confirmado no [CI da branch/PR](https://github.com/joao-henrike/EmuStack/actions); não use uma execução antiga como prova de que o HEAD atual está validado.

Última execução verde completa antes desta tranche de guardrails: [CI #110](https://github.com/joao-henrike/EmuStack/actions/runs/40947030747), SHA `36fa324de1bd6cae18122c4dcfd9b565541a9e64`. A alteração atual precisa de nova execução completa.

## P0 — integridade do modelo e das evidências

| Área | Alteração aplicada | Evidência esperada |
|---|---|---|
| Agregação do dashboard | Unificada a única função `summarize()`; métricas do modo isolado usam agentes e ambientes, enquanto o modo host usa os processos locais. | Testes em `tests/test_summarize_contract.py`. |
| Estado de boot | Separados pré-requisitos, tentativa habilitada, boot observado e smoke test; `can_boot_original` permanece como alias legado. | `tests/test_boot_state_contract.py`; UI não promete boot apenas pela presença de arquivos. |
| Relatório de validação | CI gera um Step Summary e publica um artefato Markdown por execução, com commit, resultado e limites de cobertura. | Artefato `emustack-validation-report-<run_number>` na execução correspondente. |

## P1 — contratos, instalação e recuperação

| Área | Alteração aplicada | Evidência esperada |
|---|---|---|
| Manifestos | Novo `scripts/validate-manifests.py` cruza catálogo, ambientes, sistemas, fontes, lock e Compose; a rotina `validate-project.sh` chama o validador. | `tests/test_manifest_validation.py` e validação completa no CI. |
| Instalação por perfil | `install-report.json` schema 2 traz evidências de origem/ativo/hash/caminho e estados explícitos `not-run` para execução e runtime. | `tests/test_installer.py`; endpoint `/api/report`; painel expansível na visão geral. |
| Atualização de assets | Arquivos compactados são extraídos em staging e promovidos com backup/rollback do payload e do link do launcher. | Testes de promoção bem-sucedida e rollback injetado em `tests/test_installer.py`. |
| Snapshots | Restore valida tipo/estrutura do manifesto, caminhos, duplicatas, tamanhos, hashes, contagem e total de bytes; arquivos truncados/corrompidos recebem erro claro. | Testes de snapshot adulterado/truncado e preservação do estado anterior em `tests/test_manage_storage.py`. |
| GPU opcional | Perfis Xbox One/Series sem runner foram retirados do overlay NVIDIA; o validador impede que perfis com runtime `unsupported` recebam GPU pelo overlay. | `tests/test_isolated_architecture.py` e validação Compose. |
| Guardrails de runtime | Compose aplica CPU/memória/PIDs, restart `unless-stopped` e rotação `json-file` (10m × 3); a aceitação confere a configuração efetiva de agentes e dashboard. CI executa teste isolado de auto-recuperação do agente `env-mgba`; host só com opt-in explícito. | `runtime_guardrail_issues()` em `scripts/runtime_probes.py`, `tests/test_runtime_probes.py` e CI runtime acceptance. |
| Lock upstream | Motivos de `skip-upstream` foram transformados em instruções duráveis para cada um dos nove perfis; nenhum hash foi inventado. | `scripts/check-release-lock.py --require-strict --require-pins`. |
| SBOM/CVE | CI baixa Syft/Trivy com versões e SHA-256 fixados, gera SBOM SPDX da imagem e anexa JSON de achados HIGH/CRITICAL. Política inicial é report-only para CVEs; falhas operacionais/integridade continuam bloqueando. | `supply-chain-tools.json`, `scripts/supply-chain-scan.sh` e artefatos da execução atual. |

### Persistência de saves — auditoria conservadora

- [x] Criado `save-paths.json` para os 20 perfis, distinguindo caminhos upstream documentados de perfis que ainda precisam de validação em runtime.
- [x] Criado `scripts/audit-save-layout.py`, somente de leitura, sem listagem de nomes de arquivos e sem symlinks/migrações automáticas.
- [x] Integrado o contrato de saves ao validador de manifestos e ao `validate-project.sh`; testes cobrem caminhos perigosos, diretórios ausentes, candidato observado e symlink não seguido.
- [ ] Continua pendente executar o audit em cada ambiente real, iniciar o emulador, criar um save de teste, fechar/reabrir o processo e demonstrar que o mesmo save é carregado.
- [ ] Só após a evidência por versão/build decidir se algum emulador merece configuração explícita de save path ou mapeamento dedicado para `/saves`. O conteúdo atual sob `/home/emu` continua coberto pelos snapshots, portanto não há migração automática.

## Próximas tarefas na ordem recomendada

1. **Fechar CI do HEAD atual:** aguardar a execução completa, corrigir qualquer regressão e só registrar sucesso após build + runtime acceptance.
2. **Aceitação no host real:** executar `scripts/host-doctor.py`, `scripts/validate-project.sh`, `scripts/build-and-audit.sh` e `scripts/runtime-acceptance.sh` no host alvo; registrar display, áudio, Vulkan/GPU e controle observados. CI em runner hospedado não substitui essa etapa.
3. **Boot e compatibilidade de perfis:** testar separadamente runner, pré-requisitos, boot observado, smoke test do menu e testes de jogos/homebrew legalmente obtidos. Não distribuir BIOS, firmware, chaves ou jogos proprietários.
4. **Persistência de saves:** pesquisar e validar caminhos por emulador/versão antes de criar symlinks ou mover saves. O diretório `/saves` continua sendo armazenamento separado, mas nem todos os emuladores escrevem nele por padrão; parte dos dados persiste em `/home/emu`.
5. **Segurança e cadeia de suprimentos:** SBOM SPDX e Trivy OS/library HIGH/CRITICAL estão integrados à CI com hashes verificados e política report-only inicial. Falta triar o baseline real, registrar decisões/expirações e decidir quando achados específicos podem bloquear; revisar acesso gráfico e atualizar a base Debian/snapshot após avaliação de patches.
6. **Resiliência e carga:** o runtime acceptance inclui um smoke somente leitura de 25 requests a `/api/health` com 4 workers, verifica limites efetivos e política de logs, e executa na CI uma prova de recuperação após encerrar um agente isolado. Ainda faltam testes de carga prolongada e crescimento de dados persistentes/volumes.
7. **Perfis experimentais por último:** somente reavaliar KytyPS5, shadPS4 e caminhos de dashboard/Xbox quando houver runner, artefatos oficiais/inputs reproduzíveis e evidência de runtime suficiente.

## Limites que devem permanecer explícitos

- Um relatório de instalação não prova execução do binário.
- Encontrar BIOS/firmware não prova integridade ou boot bem-sucedido.
- Um boot/menu observado não prova compatibilidade de um jogo.
- Um container saudável não prova aceleração por GPU física.
- `skip-upstream` é uma decisão de proveniência/segurança atual, não uma promessa de que um perfil será implementado futuramente.
- Não executar instalação de host, abrir portas ou alterar recursos da máquina do operador sem ação explícita no próprio host.
