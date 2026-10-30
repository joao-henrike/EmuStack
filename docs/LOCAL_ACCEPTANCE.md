# Checklist de aceitação local — EmuStack 0.7.1

> **EMUSTACK // GAMING LAB** · [README](../README.md) · [Instalação](INSTALLATION.md) · [Guia do usuário](USER_GUIDE.md) · [Matriz de emuladores](EMULATOR_MATRIX.md) · [Segurança](SECURITY.md) · [Identidade visual](IDENTIDADE-VISUAL.md)

Este guia separa os testes de código das provas que só podem ser feitas no host com Docker, sessão gráfica, drivers e arquivos de sistema autorizados.

## 1. Validação básica do host

```bash
python3 scripts/host-doctor.py
./scripts/host-setup.sh
./scripts/validate-project.sh
./scripts/build-and-audit.sh
./scripts/runtime-acceptance.sh
```

`host-setup.sh` cria 20 raízes de dados privadas e os tokens locais. Não compartilhe `.env`. O build tenta detectar/instalar apenas os projetos compatíveis com os critérios de fonte/arquitetura da versão. Consulte `install-report.json`; um perfil no catálogo não prova que o binário foi instalado.

## 2. Requisitos opcionais de vídeo, áudio e GPU

O `host-setup.sh` gera um `compose.override.yaml` para a sessão X11/XWayland e para o socket de áudio quando os encontra. Para que a checagem de aceitação exija essas integrações, execute no mesmo host/sessão gráfica:

```bash
EMUSTACK_REQUIRE_GUI=1 \
EMUSTACK_REQUIRE_AUDIO=1 \
EMUSTACK_REQUIRE_VULKAN=1 \
EMUSTACK_REQUIRE_GPU=1 \
./scripts/runtime-acceptance.sh
```

Para NVIDIA, instale e configure previamente o NVIDIA Container Toolkit no Debian; construa/inicie o projeto com `USE_NVIDIA=1` e passe a mesma variável à aceitação:

```bash
USE_NVIDIA=1 ./scripts/build-and-audit.sh
USE_NVIDIA=1 EMUSTACK_REQUIRE_VULKAN=1 EMUSTACK_REQUIRE_GPU=1 ./scripts/runtime-acceptance.sh
```

O probe Vulkan distingue um dispositivo que responde de um renderer de software como llvmpipe/lavapipe. Mesmo um probe de hardware aprovado não garante que cada emulador escolha o renderer ideal, que um jogo funcione, nem que a janela apresente corretamente a interface original.

## 3. Encaminhar um controle (opt-in)

Por segurança, nenhum dispositivo de input é mapeado por padrão. Para mapear um dispositivo já identificado como controle, especifique um único caminho `/dev/input/eventN` ou `/dev/input/jsN` e exatamente um ambiente:

```bash
EMUSTACK_INPUT_DEVICE=/dev/input/jsN \
EMUSTACK_INPUT_ENV=rpcs3 \
./scripts/host-setup.sh
```

Troque o caminho por um dispositivo que realmente exista no host e o ambiente pelo ID definido em `environments.json`. O mapeamento é somente leitura e o runtime acceptance confirma presença/mapeamento/acesso, não lê botões nem valida a configuração de teclas. Só exija o teste com `EMUSTACK_REQUIRE_INPUT=1` depois de habilitar conscientemente esse mapeamento.

## 4. Relatório automático

Após uma execução estruturalmente bem-sucedida, o script grava `data/runtime-acceptance.json` com timestamp, verificações, probes, warnings e falhas. Ele não inclui tokens nem captura eventos do controle. O relatório é local e deve ser revisado antes de compartilhar.

O mesmo acceptance executa ainda um smoke de API **somente leitura** no loopback do container do dashboard: 25 chamadas concorrentes limitadas a 4 workers para `/api/health`. O relatório/check mostra p50, p95, máximo e falhas; não chama rotas de boot/stop nem mede compatibilidade de emuladores. Esse teste é um sinal básico de estabilidade sob concorrência leve, não um benchmark de carga ou capacidade de produção.

## 5. Teste de bloqueio de requisições de agente ao dashboard

O `runtime-acceptance.sh` tenta enviar uma requisição POST a partir de cada ambiente, forjando `Host` e `X-EmuStack-Request`. Cada tentativa precisa ser recusada com HTTP 403 devido ao IP TCP de origem `.2`. O script também confere gateways, IPs estáticos e a allowlist do dashboard.

Se um probe falhar, não declare o isolamento aceito. Recolha `docker compose logs --tail=200 dashboard` e revise a faixa IPAM e a allowlist; não remova a checagem de origem para fazer o teste passar.

## 6. Boot real de sistemas originais

O runtime acceptance não inicia automaticamente todo jogo, BIOS ou dashboard. Faça os testes de boot um por vez pela seção **Sistemas originais** e verifique a janela real e os logs do agente apropriado. As rotas de PS1/DuckStation, PS2/PCSX2, PS3/RPCS3, PSP/PPSSPP, Xbox original/xemu, Wii/Dolphin e Wii U/Cemu são condicionais ou experimentais; não confunda a presença de firmware ou uma rota CLI com boot comprovado.

O XMB do PPSSPP usa `--vsh` em builds compatíveis, mas o upstream declara a pesquisa de VSH como exploratória; exige dump de firmware em `assets/flash0/` e não é uma experiência garantida. Ver a documentação oficial: <https://www.ppsspp.org/docs/getting-started/how-to-run-the-vsh/> e <https://www.ppsspp.org/docs/reference/command-line/>.

Sistemas para os quais o projeto declara `unsupported` permanecem bloqueados e não devem ser representados por uma interface HTML imitada. O EmuStack não inclui BIOS, firmware, NAND, chaves ou jogos proprietários.


## 7. Limites de recursos, rotação de logs e recuperação

A aceitação inspeciona os valores efetivos do Docker para cada agente e para o dashboard: limite de CPU, memória e PIDs, política unless-stopped, driver de logs json-file e rotação finita (max-size=10m, max-file=3). Se a configuração efetiva divergir, a aceitação falha; não basta que o YAML pareça correto.

A CI executa uma prova de recuperação opt-in que envia SIGKILL somente ao agente env-mgba, aguarda o Docker reiniciá-lo e confirma que seu endpoint de saúde volta a responder. Isso testa a política de restart, não a preservação de estado de um jogo.

No host real, essa prova não roda por padrão. Ative-a somente quando for seguro interromper esse perfil e não houver jogo com progresso não salvo:

    EMUSTACK_RUN_RECOVERY_TESTS=1 ./scripts/runtime-acceptance.sh

Não execute esse teste durante uma sessão ativa de emulação: o encerramento forçado do agente pode causar perda de progresso que ainda não foi salvo. A rotação limita cada arquivo de log a 10m e mantém até três arquivos por contêiner; isso não limita os dados gravados nos volumes persistentes.
