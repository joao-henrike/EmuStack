# ✅ Checklist de aceitação no host

Este procedimento separa a validação automatizada de código do que só pode ser verificado na máquina-alvo. Marque os resultados com host, data, commit e versão do emulador. **Um teste não executado é desconhecido, não aprovado.**

## 🧾 1. Preparação e baseline

```bash
python3 scripts/host-doctor.py
./scripts/host-setup.sh
./scripts/validate-project.sh
./scripts/build-and-audit.sh
./scripts/runtime-acceptance.sh
```

Confirme que Docker/Compose funciona, o build termina e o dashboard abre em `http://127.0.0.1:8765`. Consulte `install-report.json`: perfil de catálogo e agente saudável não significam que o binário foi instalado.

## 🧪 2. Critérios estruturais do runtime

A aceitação de runtime verifica que:

- os 20 agentes esperados iniciam e ficam saudáveis;
- cada agente usa mounts e rede específicos;
- o dashboard tem os mounts/rede de controle esperados e não publica portas diretamente;
- `dashboard-proxy` está saudável, com filesystem read-only, sem capabilities e com somente duas redes dedicadas;
- a publicação aparece ativa em `NetworkSettings.Ports` e está vinculada somente a `127.0.0.1:8765` no proxy;
- flags de hardening e IPs/allowlist correspondem ao modelo documentado;
- cada agente tenta acessar endpoints protegidos do dashboard com cabeçalhos forjados; a solicitação de controle/metadados deve ser recusada;
- health/capability endpoints respondem conforme seu contrato;
- sistemas marcados não suportados continuam bloqueados.

Se algum desses checks falhar, **não remova a validação de origem, token ou caminho para fazer o teste passar**. Guarde logs e corrija a causa.

O ciclo de vida do dashboard é deliberadamente independente do resultado dos healthchecks: ele aguarda os contêineres dos agentes iniciarem, mas pode ficar disponível enquanto um ou mais agentes ainda estão offline. Isso permite consultar o painel e diagnosticar falhas parciais. Essa disponibilidade degradada **não** aprova o ambiente: esta etapa de aceitação continua exigindo os 20 agentes saudáveis e todas as verificações de isolamento aprovadas.


## 🖥️ 3. GUI, áudio, Vulkan e GPU

Execute no mesmo host e sessão de desktop em que a stack será utilizada:

```bash
EMUSTACK_REQUIRE_GUI=1 EMUSTACK_REQUIRE_AUDIO=1 EMUSTACK_REQUIRE_VULKAN=1 EMUSTACK_REQUIRE_GPU=1 ./scripts/runtime-acceptance.sh
```

Para NVIDIA, configure drivers e NVIDIA Container Toolkit primeiro:

```bash
USE_NVIDIA=1 ./scripts/build-and-audit.sh
USE_NVIDIA=1 EMUSTACK_REQUIRE_VULKAN=1 EMUSTACK_REQUIRE_GPU=1 ./scripts/runtime-acceptance.sh
```

Interpretação:

| Probe | Significado | Não prova |
|---|---|---|
| GUI | O container consegue alcançar a infraestrutura gráfica detectada. | Janela correta ou boot completo. |
| Áudio | O caminho/socket testado responde. | Som correto em todos os jogos. |
| Vulkan | A API enumera/disponibiliza dispositivo esperado. | Escolha do backend ideal pelo emulador. |
| GPU | O probe distingue hardware de renderers de software conhecidos. | Desempenho ou compatibilidade título a título. |

`llvmpipe`/`lavapipe` normalmente representam renderização de software no contexto do probe. Um runtime CI sem tela/GPU física não equivale à aceitação da sua máquina.

## 🎮 4. Controle (opt-in e mínimo privilégio)

Mapeie exatamente um controle para exatamente um ambiente. Confirme o node de dispositivo; não escolha teclado ou mouse.

```bash
EMUSTACK_INPUT_DEVICE=/dev/input/js0 EMUSTACK_INPUT_ENV=rpcs3 ./scripts/host-setup.sh
EMUSTACK_REQUIRE_INPUT=1 ./scripts/runtime-acceptance.sh
```

O probe verifica presença/acesso e configuração de mapeamento; não executa uma validação completa de botões dentro de todos os emuladores. Faça um teste interativo adicional em cada perfil necessário.

## 📄 5. Relatórios

A aceitação salva `data/runtime-acceptance.json`; o diagnóstico do host com `--write` grava `data/host-capabilities.json`. Esses relatórios podem registrar sistema operacional, arquitetura, GPU, paths e detalhes do ambiente. Revise antes de compartilhar e nunca compartilhe `.env`, conteúdo de firmware ou saves pessoais.

## 🛠️ 5.1 Validação do gerenciamento de executáveis (Fase 1)

Sem executar código upstream, valide o catálogo do host:

```bash
python3 scripts/emulator-manager.py status
python3 scripts/emulator-manager.py deps kytyps5
python3 scripts/emulator-manager.py deps shadps4
python3 scripts/emulator-manager.py deps ppsspp
python3 scripts/emulator-manager.py deps melonds
python3 scripts/emulator-manager.py deps bsnes
python3 -m unittest discover -s tests -p 'test_emulator_manager.py' -v
```

O gerenciador **não certifica** a execução apenas pelo hash: `binary_signature` é uma pista estática de formato, `managed_hash_valid` prova integridade perante seu estado registrado e `execution_tested` permanece falso até um teste real. Para cada receita registre compilador, dependências, commit, log e SHA-256. Repita instalação e rollback com o emulador encerrado. Veja [Fase 1](EMULATOR_MANAGER.md).

### Evidência de build de 31/10/2026

O relatório local mostrou **bsnes instalado** com `runtime_tested: false`. Os outros quatro builds foram bloqueados por submódulos internos (KytyPS5/shadPS4/PPSSPP) ou Qt6 ausente (melonDS). Os comandos `plan-deps` e `sync-deps` já foram executados no host com êxito: KytyPS5 (14), shadPS4 (54), PPSSPP (28) submódulos internos. No build posterior, melonDS continuou sem Qt6 pois o comando APT foi simulação; PPSSPP exigiu SDL3 em vez de SDL2; KytyPS5 e shadPS4 consultaram incorretamente o SHA do EmuStack para os prebuilds de FFmpeg. Os metadados Git temporários e a receita SDL3 foram corrigidos, ainda sem reexecução no host. Execute novamente os testes e registre hashes antes de afirmar que o software é executável.

## 🧱 6. Boot real por sistema/jogo

Para cada perfil que pretende usar, faça um teste com arquivos que você tem direito de utilizar. Registre o resultado de forma separada para:

1. executável detectado;
2. janela do emulador abre;
3. renderer/hardware observado;
4. firmware/BIOS aceito quando necessário;
5. sistema/menu original chega à tela esperada (quando essa função existe);
6. jogo/homebrew chega ao estado jogável;
7. áudio, entrada, controles, save/load e encerramento.

Uma rota implementada ou pré-requisitos detectados não são evidência de sucesso visual. Veja [Sistemas originais](ORIGINAL_SYSTEM_UI.md) e [Matriz](EMULATOR_MATRIX.md).

## 📋 Modelo de registro de aceitação

| Campo | Valor a registrar |
|---|---|
| Data, host e commit | |
| Sistema operacional/kernel/arquitetura | |
| Docker/Compose e método de build | |
| Perfil + binário + versão/hash | |
| Jogo/homebrew e hash (sem publicar o arquivo) | |
| Renderização e driver | |
| Boot / jogabilidade | |
| GUI / áudio / controle / save-load | |
| Falhas, warnings, logs sanitizados | |

## 🔍 7. Diagnóstico quando falha

```bash
docker compose ps
docker compose logs --tail=200 dashboard
docker compose logs --tail=200 env-rpcs3
curl -i http://127.0.0.1:8765/api/health
```

Troque `env-rpcs3` pelo agente relevante. Veja o [guia de troubleshooting](TROUBLESHOOTING.md). O resultado é válido apenas para a configuração e o hardware testados.
