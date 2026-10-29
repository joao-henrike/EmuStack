# ⚙️ Configuração e variáveis

O arquivo `.env.example` documenta as variáveis esperadas. O caminho recomendado é executar `./scripts/host-setup.sh`, que prepara o `.env` real e as raízes de dados. **Mantenha o `.env` privado.**

## 👥 Identidade do processo

| Variável | Padrão/documento | Função |
|---|---|---|
| `PUID` | UID do usuário que executa o setup | UID usado para alinhar permissões entre o host e os contêineres. |
| `PGID` | GID correspondente | GID usado para alinhar permissões. |
| `EMUSTACK_AGENT_TOKEN_<ID>` | Gerada pelo setup para cada um dos 20 IDs | Token individual dashboard↔agente; não use valor único compartilhado. |

O script prepara segredos aleatórios e restringe as permissões do `.env`. Se rodar novamente, revise o que foi preservado antes de alterar tokens ou overrides manualmente.

## 🧠 Limites de recursos

Os limites são tetos de contêiner, não reservas nem promessa de performance. Os ambientes compartilham CPU, memória, disco, GPU e kernel do host.

| Variável | Valor exemplificado no `.env.example` | Aplicação |
|---|---:|---|
| `EMUSTACK_CPU_LIMIT` | `2` | Dashboard/serviço central. |
| `EMUSTACK_MEMORY_LIMIT` | `1g` | Memória do serviço central. |
| `EMUSTACK_PIDS_LIMIT` | `256` | Processos do serviço central. |
| `EMUSTACK_CLI_CPU_LIMIT` | `2` | Serviço CLI de manutenção/build. |
| `EMUSTACK_CLI_MEMORY_LIMIT` | `2g` | Memória do serviço CLI. |
| `EMUSTACK_CLI_PIDS_LIMIT` | `128` | Processos do serviço CLI. |
| `EMUSTACK_ENV_CPU_LIMIT` | `6` | Teto por agente de ambiente. |
| `EMUSTACK_ENV_MEMORY_LIMIT` | `5g` | Teto por agente. |
| `EMUSTACK_ENV_PIDS_LIMIT` | `512` | Teto de processos por agente. |
| `EMUSTACK_MAX_ACTIVE_ENVIRONMENTS` | `2` | Número máximo de ambientes ativos em paralelo. |
| `EMUSTACK_MAX_ACTIVE_PER_ENV` | `2` | Limite de sessões ativas por perfil. |

Ajuste após medir memória e CPU reais. Não aumente tudo simultaneamente em um host com RAM limitada; a GPU e a memória do desktop também consomem recursos.

## 📦 Build e assets upstream

| Variável/sinalizador | Uso | Efeito/limite |
|---|---|---|
| `APT_SNAPSHOT_TIMESTAMP` | ID de snapshot Debian, como `20261027T000000Z` | Congela a origem de pacotes APT nessa data; pode perder correções de segurança posteriores. |
| `INSTALL_UPSTREAM=0` | Desativar downloads de releases upstream | Útil em build offline/rápido, mas pode deixar perfis sem assets. |
| `BUILD_KYTYPS5=0` | Desabilitar build opcional de KytyPS5 | O lock atual não pinou/validou a compilação fonte do KytyPS5. |
| `KYTYPS5_REF` | Tag upstream documentada no exemplo | Referência candidata do build opcional. |
| `KYTYPS5_EXPECTED_SHORT` | Prefixo de commit esperado | Checagem de consistência para esse caminho específico; não amplia o escopo do release-lock. |
| `USE_NVIDIA=1` | Prefixo do comando de build/aceitação | Inclui `compose.nvidia.yaml` para conceder GPU aos agentes. |
| `FREEZE_RELEASE_LOCK=1` | Prefixo de `build-and-audit.sh` | Tenta exportar hashes de assets efetivamente baixados e rebuildar usando lock estrito. |

Exemplo de build com snapshot APT datado e release lock:

```bash
APT_SNAPSHOT_TIMESTAMP=20261027T000000Z FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh
```

Isso não promete reprodutibilidade bit a bit: arquitetura, BuildKit, toolchain e builds upstream também influenciam o resultado.

## 🖥️ Capacidades opcionais do host

`host-setup.sh` pode gerar `compose.override.yaml` para X11/XWayland e áudio Pulse compatível quando as condições locais existem. O override é um arquivo de configuração de máquina; confira antes de publicar.

| Sinalizador de aceitação | O teste torna-se obrigatório |
|---|---|
| `EMUSTACK_REQUIRE_GUI=1` | Acesso ao display disponível no runtime. |
| `EMUSTACK_REQUIRE_AUDIO=1` | Comunicação com a infraestrutura de áudio testável. |
| `EMUSTACK_REQUIRE_VULKAN=1` | Inicialização/listagem Vulkan esperada. |
| `EMUSTACK_REQUIRE_GPU=1` | Dispositivo de hardware, não somente renderer de software, conforme probe. |
| `EMUSTACK_REQUIRE_INPUT=1` | Presença/acesso ao dispositivo de controle explicitamente mapeado. |

As variáveis tornam um probe requisito; não adicionam magicamente um dispositivo ao contêiner. Configure a integração primeiro e rode a aceitação na mesma sessão/host.

## 🕹️ Mapeamento de controle

Defina as duas variáveis em conjunto:

```bash
EMUSTACK_INPUT_DEVICE=/dev/input/js0 EMUSTACK_INPUT_ENV=rpcs3 ./scripts/host-setup.sh
```

`EMUSTACK_INPUT_DEVICE` deve identificar um único `/dev/input/eventN` ou `/dev/input/jsN` existente. `EMUSTACK_INPUT_ENV` deve ser exatamente um dos IDs documentados em `environments.json`. Não mapeie teclado/mouse nem o diretório `/dev/input` inteiro.

## 🧹 Quando alterar configurações

Após mudar tokens, limites, GPU ou dispositivos, recrie os serviços usando a mesma lista de manifests Compose utilizada para subi-los. Em dúvida, consulte [Instalação](INSTALLATION.md), [Aceitação local](LOCAL_ACCEPTANCE.md) e [Solução de problemas](TROUBLESHOOTING.md).
