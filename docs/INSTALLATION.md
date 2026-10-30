# Instalação — EmuStack 0.7.1

> **EMUSTACK // GAMING LAB** · [README](../README.md) · [Instalação](INSTALLATION.md) · [Guia do usuário](USER_GUIDE.md) · [Matriz de emuladores](EMULATOR_MATRIX.md) · [Segurança](SECURITY.md) · [Identidade visual](IDENTIDADE-VISUAL.md)

## Pré-requisitos

- Linux x86-64 (ambiente principal: Debian 13).
- Docker Engine e Docker Compose v2 funcionando para o usuário que executará o projeto.
- Espaço em disco para uma imagem grande, builds de fonte opcionais e assets oficiais baixados.
- Para interfaces gráficas: uma sessão X11/XWayland funcional; para áudio/controladores, os sockets/dispositivos corretos do host.

## Sequência recomendada

```bash
chmod +x scripts/host-setup.sh scripts/build-and-audit.sh scripts/validate-project.sh scripts/runtime-acceptance.sh
./scripts/host-setup.sh
./scripts/validate-project.sh
./scripts/build-and-audit.sh
./scripts/runtime-acceptance.sh
```

`host-setup.sh` prepara as vinte raízes `data/environments/<id>/`, cria `.env` de modo privado e gera 20 tokens aleatórios distintos, um por agente, para a comunicação dashboard-agentes. É seguro executar novamente: preserva o token e os limites já configurados, mas não importa automaticamente dados antigos.

`build-and-audit.sh` executa a bateria de testes/validações, confere a configuração Docker Compose, constrói a imagem, gera o relatório de ativos upstream, executa diagnóstico e sobe o dashboard. A URL é `http://127.0.0.1:8765`.

Para usar os serviços manualmente, inclua o override gerado sempre que existir:

```bash
docker compose -f compose.yaml -f compose.override.yaml config --quiet
docker compose -f compose.yaml -f compose.override.yaml up -d dashboard
docker compose -f compose.yaml -f compose.override.yaml ps
```

Se não houver `compose.override.yaml`, use somente `-f compose.yaml`.

## NVIDIA

Depois de instalar e testar o NVIDIA Container Toolkit no host:

```bash
USE_NVIDIA=1 ./scripts/build-and-audit.sh
```

Isso adiciona o mapeamento de GPU aos perfis que possuem runner conhecido no overlay opcional. Os placeholders Xbox One/Series sem runner ficam fora dessa passagem. O overlay não instala magicamente drivers válidos nem garante aceleração em cada emulador; confirme o renderer em execução.

## Acceptance de vídeo, áudio e GPU

Se está numa sessão X11/XWayland com áudio e quer que esses itens sejam requisitos obrigatórios, rode:

```bash
EMUSTACK_REQUIRE_GUI=1 EMUSTACK_REQUIRE_AUDIO=1 EMUSTACK_REQUIRE_VULKAN=1 EMUSTACK_REQUIRE_GPU=1 ./scripts/runtime-acceptance.sh
```

O acceptance testa reachability da tela/áudio e se Vulkan enumera uma GPU que não seja apenas software. Ele não executa jogos nem prova boot do firmware. Veja `docs/LOCAL_ACCEPTANCE.md` para todos os sinalizadores e diagnósticos.

## Controle opcional

O mapeamento do controle é explicitamente opt-in e limitado a um dispositivo e um ambiente. Exemplo (confirme primeiro o node correto, não escolha teclado/mouse):

```bash
EMUSTACK_INPUT_DEVICE=/dev/input/js0 EMUSTACK_INPUT_ENV=rpcs3 ./scripts/host-setup.sh
```

O caminho precisa existir como dispositivo de caracteres e ser `/dev/input/eventN` ou `/dev/input/jsN`. O script salva a configuração em `.env`.

## Upgrade de 0.4.x ou anterior

A versão 0.7.1 deixa de montar os diretórios compartilhados `data/games`, `data/bios`, `data/saves` e `data/home`. Faça cópias de backup e migre manualmente cada item para a raiz apropriada em `data/environments/<id>/`. Não apague o diretório antigo até confirmar jogos, saves, configurações e firmware no perfil certo.

## Relatório individual por perfil

Depois de construir a imagem e iniciar o dashboard, a visão geral exibe **Relatório de instalação**. Expanda cada perfil para inspecionar status, origem/artefato, versão quando conhecida, hash esperado e calculado, caminho do binário e os estados separados de teste de execução e runtime.

Os estados `not-run` / **Não executado** são deliberados: o build não abre todos os GUIs nem comprova que cada sistema original ou jogo inicia. A arquitetura apresentada é a que o processo de instalação observou dentro do seu contexto; ela não certifica o hardware físico nem a GPU do computador final. Para investigar a máquina real, use `scripts/host-doctor.py` e `scripts/runtime-acceptance.sh`, e documente boots/jogos separadamente.

## Verificação

```bash
./scripts/validate-project.sh
./scripts/runtime-acceptance.sh
docker compose ps
docker compose logs --tail=200 dashboard
docker compose logs --tail=200 env-pcsx2
```

Um agente online não significa que seu binário de emulador foi instalado nem que um jogo/firmware funciona. Use **Relatório de instalação**, **Ambientes isolados** e os logs do perfil para conferir cada camada separadamente.
