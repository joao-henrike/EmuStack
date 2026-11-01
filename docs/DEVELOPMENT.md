# 🧑‍💻 Desenvolvimento e contribuição

**Desenvolvimento da Fase 1:** usar `bash scripts/phase1.sh validate` e o builder Docker para os cinco perfis em vez de instalar toolchains no host. A revisão dos commits fonte, bibliotecas runtime, pacotes completos e limitações de hardware é obrigatória. [Checklist](PHASE1_IMPLEMENTATION.md).

Este guia descreve como mudar EmuStack sem enfraquecer os limites de segurança ou confundir capacidade planejada com comportamento testado.

## 🧰 Ambiente

- Linux com Python 3 e Docker Engine/Compose v2 para build completo.
- Node.js para rodar os testes JS (o script pode pular essa parte quando Node não existe).
- PyYAML é usado no workflow de CI para validar os manifests Compose.
- Conectividade com upstream somente para testes/builds que baixem assets. O caminho de validação estática deve ser executado antes do build.

## 🚦 Fluxo recomendado

```bash
git checkout -b docs-or-feature/minha-mudanca
./scripts/validate-project.sh
docker compose -f compose.yaml config --quiet
```

Implemente uma alteração pequena e rastreável. Rode os testes relevantes, em seguida o fluxo completo no host quando a mudança afetar Compose, rede, mounts, build, GUI, áudio ou lançamento. Abra PR com motivação, escopo, risco, comandos executados, resultados e limitações ainda abertas.

## 🗂️ Fontes de verdade: mantenha os manifestos alinhados

- `catalog.json`: IDs de emuladores/launchers, metadados, comandos e reconhecimento.
- `environments.json`: exatamente 20 IDs de ambientes; limites/estratégia por ambiente.
- `console-systems.json`: IDs e estados de boot do sistema/menu original.
- `game-sources.json`: fontes, avisos e mapeamento para os perfis.
- `release-lock.json`: estado de instalação pinada e razões de `skip-upstream`.
- `compose.yaml`: serviços reais, IPAM, mounts, hardening e allowlist.
- `compose.nvidia.yaml`: override opcional para a passagem de GPU.
- `webapp.py`, `console_agent.py`, `console_modes.py`: autorização, API e estratégia de lançamento.
- `tests/`: testes de regressão e contratos que precisam acompanhar novos comportamentos.

Ao adicionar/remover um ID, atualize todos os manifestos, os serviços, as redes/allowlist, as páginas da matriz e os testes de consistência. Não adicione um perfil apenas para aumentar a contagem.

## 🛠️ Desenvolvimento do gerenciador de instalação por perfil

O código de host em `scripts/emulator-manager.py` mantém receitas de build permitidas, checagem de pin, importação com SHA-256 e backup/rollback. As regressões estão em `tests/test_emulator_manager.py`; a cobertura estrutural não substitui compilar upstream real num host. Veja [Gerenciador de emuladores](EMULATOR_MANAGER.md) para os cinco projetos com receita explícita e critérios de aceite.

## 🧪 Testes obrigatórios por tipo de alteração

| Alteração | Validação mínima |
|---|---|
| Lógica Python/API | `./scripts/validate-project.sh` e testes específicos novos. |
| JavaScript/UI | `node --check` e testes JS existentes; teste visual no navegador quando necessário. |
| Shell/build | `bash -n`/`sh -n`, script de validação e build relevante. |
| Manifestos/catalog | JSON válido, igualdade de IDs, integridade dos links/refs e testes de contratos. |
| Docker/segurança/rede | `docker compose config --quiet`, build e `runtime-acceptance.sh` no Docker real. |
| Emulator command/firmware | Documentar upstream/version; teste manual com files/host autorizados e resultado explícito. |
| Lock de assets | Validar asset oficial, hash, cobertura e rebuild estrito; não inventar hash. |
| Documentação | Verificar links relativos, comandos reais, status, flags e ausência de segredos/claims superlativas. |

O CI existente roda os testes e validações do workflow. O resultado deve ser consultado no PR/commit específico; uma aprovação antiga não se transfere automaticamente para a mudança nova.

## 🛡️ Guardrails não negociáveis

- Não remover allowlist de origem, tokens por agente, validação de ID/path, mounts privados, hardening ou probes de segurança apenas para fazer um teste passar.
- Não aceitar shell ou binário arbitrário vindo de input do navegador.
- Não usar symlink para unir raízes dos ambientes.
- Não declarar suporte a menu/jogo com base apenas em arquivo presente ou argumento CLI.
- Não converter `skip-upstream` em um falso sucesso ou baixar binários de fontes não verificadas.
- Não introduzir ROMs, dumps proprietários, tokens reais, arquivos de host ou relatórios sensíveis no git.
- Não documentar teste como concluído se ele não foi executado.

## 📝 Formato sugerido de Pull Request

Inclua:
1. **Motivação e alteração:** comportamento antes/depois.
2. **Superfície de impacto:** perfil, manifestos, rede, storage, API, GUI etc.
3. **Validação executada:** comando e resultado.
4. **Validação não executada:** host/GPU/firmware/jogos não disponíveis.
5. **Segurança e migração:** efeitos sobre paths, tokens e dados persistentes.
6. **Documentação:** links/guia atualizado.

## 🔍 Convenções para documentação

Use tabelas curtas, comandos copiáveis, ícones para navegação (não para mascarar incerteza), links relativos dentro de `docs/` e estados que distingam “disponível”, “experimental”, “condicional” e “não suportado”. Atualize `CHANGELOG.md` quando a alteração visível merecer registro.
