# 🔄 Releases, assets e atualização

**Fase 1:** a compilação pinada gera pacote completo por perfil e launcher cuja versão é rastreável; versões anteriores preservam executável, metadados e recursos. Use `bash scripts/phase1.sh history <id>`, `rollback` e `uninstall`, sem editar hashes manualmente. O release lock de ativos Docker é separado deste histórico. [Detalhes](PHASE1_IMPLEMENTATION.md).

## 🎯 Princípio

A atualização de upstream pode alterar código, artefatos, comandos, dependências e comportamento. EmuStack mantém o lock estrito para assets efetivamente baixados e validados; não transforma mudanças upstream em compatibilidade garantida.

## 📌 Antes de atualizar

1. Leia as notas/release e a licença oficial de cada projeto afetado.
2. Confirme o asset para Linux/arquitetura esperado e a origem oficial.
3. Confira se o comando e o nome do binário batem com `catalog.json`/Dockerfile.
4. Valide SHA-256 usando o fluxo do projeto; registre a referência utilizada.
5. Execute a validação estática, build, lock estrito e runtime acceptance.
6. Teste no host a GUI e ao menos um título/homebrew permitido por perfil alterado.
7. Atualize matriz, build docs, troubleshooting e changelog com o que foi realmente observado.

## 🧊 Workflow de atualização do release lock

O workflow **Freeze official emulator release assets** está configurado para início manual (`workflow_dispatch`) em GitHub Actions.

1. Abra [Actions](https://github.com/joao-henrike/EmuStack/actions) e selecione o workflow.
2. Acione-o na branch desejada e observe logs completos.
3. Confirme que o build de descoberta e a exportação do lock terminaram com sucesso.
4. Baixe o artifact `release-lock.json` e revise o diff, URLs, tags, hashes e motivos de itens ignorados.
5. Verifique o rebuild em modo estrito.
6. Incorpore o arquivo revisado por PR, com validações e descrição da mudança.
7. Repita runtime acceptance e teste manual dos perfis cuja versão mudou.

**Não substitua o lock só porque o workflow gerou um artifact.** Se houver um download inesperado, falha de hash, tag não oficial ou asset fora da arquitetura esperada, interrompa a atualização e investigue.

## 🧱 O que o lock cobre e não cobre

- A imagem base Debian está fixada por digest.
- Versões APT não são temporalmente fixas por padrão; `APT_SNAPSHOT_TIMESTAMP` escolhe um snapshot, que também congela correções posteriores.
- 11 assets upstream têm hash no lock atual; nove IDs usam `skip-upstream` e motivo.
- Compilação fonte opcional de KytyPS5 não está coberta pelo lock atual.
- O lock não fixa a licença/direito de cada jogo/BIOS/firmware, não testa o boot e não promete build bit a bit em qualquer host.

Detalhes e exemplo de comando em [Build e reprodutibilidade](BUILD_REPRODUCIBILITY.md).

## 🧾 Evidência e changelog

Cada atualização deve capturar: commit, referência upstream, asset/URL, SHA-256, plataforma de build, resultado do build, tests/acceptance e falhas conhecidas. Atualize `CHANGELOG.md` e a matriz por perfil. Diferencie “CI verde”, “build concluído” e “jogo testado”.

## 🛠️ Binários locais e atualização por perfil (Fase 1)

O `scripts/emulator-manager.py` gerencia somente binários extras na pasta privada `data/environments/<id>/emulators/`. Os comandos `status`, `deps`, `build`, `install-file`, `history`, `rollback` e `uninstall` não alteram hashes do Docker nem atualizam silenciosamente o upstream. Primeiro revise `python3 scripts/upstream-manager.py plan`, faça `pin` somente em branch de revisão, e depois compile explicitamente. Há cinco receitas de build de fonte Linux registradas; execução real exige aceitação no Debian. Leia [Fase 1 — Gerenciador](EMULATOR_MANAGER.md).

## 🧯 Rollback

Antes de substituir assets ou atualizar o ambiente local, faça backup dos dados persistentes afetados. Preserve o lock anterior e o commit anterior para rollback. Se um binário/regressão falhar, reverta a alteração rastreável em vez de editar hash ou remover testes para ocultar a falha.
