# EmuStack — status da execução do roteiro

Este documento acompanha a execução incremental das correções prioritárias. O estado de integração da versão atual deve ser confirmado no [CI da branch/PR](https://github.com/joao-henrike/EmuStack/actions); não use uma execução antiga como prova de que o HEAD atual está validado.

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
| Lock upstream | Motivos de `skip-upstream` foram transformados em instruções duráveis para cada um dos nove perfis; nenhum hash foi inventado. | `scripts/check-release-lock.py --require-strict --require-pins`. |

## Próximas tarefas na ordem recomendada

1. **Fechar CI do HEAD atual:** aguardar a execução completa, corrigir qualquer regressão e só registrar sucesso após build + runtime acceptance.
2. **Aceitação no host real:** executar `scripts/host-doctor.py`, `scripts/validate-project.sh`, `scripts/build-and-audit.sh` e `scripts/runtime-acceptance.sh` no host alvo; registrar display, áudio, Vulkan/GPU e controle observados. CI em runner hospedado não substitui essa etapa.
3. **Boot e compatibilidade de perfis:** testar separadamente runner, pré-requisitos, boot observado, smoke test do menu e testes de jogos/homebrew legalmente obtidos. Não distribuir BIOS, firmware, chaves ou jogos proprietários.
4. **Persistência de saves:** pesquisar e validar caminhos por emulador/versão antes de criar symlinks ou mover saves. O diretório `/saves` continua sendo armazenamento separado, mas nem todos os emuladores escrevem nele por padrão; parte dos dados persiste em `/home/emu`.
5. **Segurança e cadeia de suprimentos:** adicionar SBOM/varredura de vulnerabilidades com versões de ferramentas fixadas e política explícita para alertas; avaliar o acesso por recurso gráfico e atualizar a base Debian/snapshot após revisão de patches.
6. **Resiliência e carga:** testar reinícios de agente, requests concorrentes, limites de CPU/RAM/PIDs, recuperação após falha e crescimento de logs/armazenamento.
7. **Perfis experimentais por último:** somente reavaliar KytyPS5, shadPS4 e caminhos de dashboard/Xbox quando houver runner, artefatos oficiais/inputs reproduzíveis e evidência de runtime suficiente.

## Limites que devem permanecer explícitos

- Um relatório de instalação não prova execução do binário.
- Encontrar BIOS/firmware não prova integridade ou boot bem-sucedido.
- Um boot/menu observado não prova compatibilidade de um jogo.
- Um container saudável não prova aceleração por GPU física.
- `skip-upstream` é uma decisão de proveniência/segurança atual, não uma promessa de que um perfil será implementado futuramente.
- Não executar instalação de host, abrir portas ou alterar recursos da máquina do operador sem ação explícita no próprio host.
