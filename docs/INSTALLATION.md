# 🛠️ Instalação do EmuStack 0.7.1

Este guia conduz do clone até o primeiro dashboard. Para limites de recursos e todas as variáveis, consulte [Configuração](CONFIGURATION.md).

## ✅ Requisitos

- Linux x86-64; ambiente de referência: Debian 13.
- Docker Engine funcionando e plugin **Docker Compose v2**.
- Usuário com permissão para acessar o daemon Docker.
- Rede para baixar pacotes/assets no build inicial; espaço para imagem, cache, executáveis, jogos e arquivos de sistema do usuário.
- Opcional: X11/XWayland, socket de áudio PulseAudio/PipeWire compatível, NVIDIA Container Toolkit, Vulkan e um controle específico.
- Para menus/jogos: arquivos de sistema obtidos e utilizados legalmente, quando exigidos pelo emulador.

O build instala somente assets que passam pelas regras da versão. Um perfil sem binário compatível continua listado com estado de instalação correspondente; isso é intencional.

## 🚀 Instalação inicial

```bash
git clone https://github.com/joao-henrike/EmuStack.git
cd EmuStack
python3 scripts/host-doctor.py
./scripts/host-setup.sh
./scripts/validate-project.sh
./scripts/build-and-audit.sh
./scripts/runtime-acceptance.sh
```

Abra **http://127.0.0.1:8765** na mesma máquina. Se o `host-setup.sh` detectar uma sessão X11/XWayland ou áudio compatível, ele pode gerar `compose.override.yaml` com a integração opt-in. O script de build usa esse override explicitamente quando existe.

### O que cada comando faz

1. `host-doctor.py` inventaria recursos e ferramentas sem modificar drivers/dispositivos.
2. `host-setup.sh` cria 20 raízes de dados, gera tokens distintos e protege o `.env`; também detecta integrações locais opcionais.
3. `validate-project.sh` executa testes Python, verificações de sintaxe, testes JavaScript quando Node.js está instalado, sintaxe shell e validação do lock.
4. `build-and-audit.sh` valida Compose, constrói a imagem, registra os assets detectados e inicia a stack.
5. `runtime-acceptance.sh` executa os probes de runtime no daemon Docker do host atual.

## 🧭 Subir ou inspecionar manualmente

Se o host setup gerou um override, inclua-o em cada comando manual que precise das integrações:

```bash
docker compose -f compose.yaml -f compose.override.yaml config --quiet
docker compose -f compose.yaml -f compose.override.yaml ps
docker compose -f compose.yaml -f compose.override.yaml logs --tail=200 dashboard
```

Sem override, use apenas `-f compose.yaml`. Os caminhos explícitos `-f` impedem que o Compose descubra automaticamente arquivos não incluídos na invocação.

## 🖥️ Gráficos, áudio e NVIDIA

A integração gráfica gerada depende da sessão e das permissões do host. Execute `host-setup.sh` **a partir da sessão de desktop que será utilizada**. Wayland puro, XWayland, sockets, drivers e políticas de segurança podem mudar o resultado.

Para NVIDIA, configure previamente os drivers e o NVIDIA Container Toolkit no host e então:

```bash
USE_NVIDIA=1 ./scripts/build-and-audit.sh
USE_NVIDIA=1 EMUSTACK_REQUIRE_VULKAN=1 EMUSTACK_REQUIRE_GPU=1 ./scripts/runtime-acceptance.sh
```

A opção concede GPU aos agentes; não instala drivers de host nem garante que cada emulador utilize aceleração. `llvmpipe`/`lavapipe` indicam renderização de software para estes testes, não aceleração NVIDIA.

Para tornar obrigatórios os probes de desktop e áudio, use:

```bash
EMUSTACK_REQUIRE_GUI=1 EMUSTACK_REQUIRE_AUDIO=1 ./scripts/runtime-acceptance.sh
```

Leia [Aceitação local](LOCAL_ACCEPTANCE.md) para a combinação completa de requisitos e a tabela de critérios.

## 🎮 Controle (opcional)

Nenhum dispositivo de entrada é encaminhado por padrão. Identifique um controle sem escolher teclado/mouse e passe **um único dispositivo** para **um único perfil**:

```bash
EMUSTACK_INPUT_DEVICE=/dev/input/js0 EMUSTACK_INPUT_ENV=rpcs3 ./scripts/host-setup.sh
EMUSTACK_REQUIRE_INPUT=1 ./scripts/runtime-acceptance.sh
```

Use o caminho real que existir no host. Revise `compose.override.yaml` e `.env`; não compartilhe esses arquivos sem verificar se contêm dados locais.

## 🔐 Arquivos e privacidade

- Não faça commit de `.env`, `compose.override.yaml`, dumps, logs com dados pessoais ou snapshots.
- O `.env` contém um token por agente. Não substitua todos por um token compartilhado.
- Revise os relatórios `data/host-capabilities.json`, `install-report.json` e `data/runtime-acceptance.json` antes de publicar: inventários podem revelar detalhes do host/caminhos locais.
- Não instale executáveis aleatórios em `data/environments/<id>/emulators/`; os nomes precisam corresponder aos launchers reconhecidos.

## 💾 Atualizar uma instalação antiga

A versão 0.7.1 não monta mais as pastas compartilhadas legadas `data/games/`, `data/bios/`, `data/saves/` e `data/home/`. Antes de atualizar:
1. Faça backup dos dados antigos e confirme que o arquivo de backup abre.
2. Mova cada jogo/BIOS/save/configuração para `data/environments/<id>/` do sistema correto.
3. Não apague a cópia antiga até confirmar o conteúdo pela interface e pelo emulador.
4. Execute a validação e a aceitação do novo runtime.

Não há migração automática de conteúdo entre perfis.

## ⏹️ Parar e retomar

Para encerrar os serviços sem apagar os dados bind-mounted:

```bash
docker compose -f compose.yaml down
```

Se uma configuração GUI/NVIDIA foi usada, repita os mesmos arquivos `-f` com que a stack foi criada. Não acrescente `--volumes` sem entender quais volumes estão definidos. Os dados persistentes normais ficam em `data/environments/<id>/` no checkout.

## 🧪 Diagnóstico básico

```bash
docker compose ps
docker compose logs --tail=200 dashboard
docker compose logs --tail=200 env-rpcs3
curl -i http://127.0.0.1:8765/api/health
```

Se os logs indicarem falta de executável, consulte o relatório de instalação antes de atribuir a falha ao jogo. Para investigar erros específicos, use [Solução de problemas](TROUBLESHOOTING.md).
