# 🔌 Referência de API e CLI

**CLI de operações (não é API do dashboard):** `bash scripts/phase1.sh` fornece `status`, `deps`, `plan-deps`, `sync-deps`, `build`, `build-all`, `install-file`, `history`, `rollback`, `uninstall`, `purge` (com confirmação destrutiva), `logs`, `test` e `validate`. Não foi adicionada permissão de build ao dashboard. Consulte [referência Fase 1](PHASE1_IMPLEMENTATION.md).

> [!WARNING]
> Esta é a API interna da versão 0.7.1, destinada à UI local e à comunicação entre dashboard e agentes. **Não é uma API pública estável.** Não exponha a porta, não use reverse proxy nem transforme os endpoints internos de agentes em endpoints acessíveis pela LAN.

## 🛠️ Gerenciador exclusivo do host

`scripts/emulator-manager.py` é uma CLI separada das APIs. Os comandos `status`, `deps`, `plan-deps`, `sync-deps`, `build`, `build-all`, `install-file`, `history`, `rollback` e `uninstall` emitem JSON ou erros em stderr. `status` exibe metadados do release lock, formato estático do binário gerenciado e estado da instalação, sem afirmar jogabilidade. **Não existem endpoints HTTP para instalar, atualizar ou apagar executáveis**, preservando a fronteira de privilégios do dashboard. Leia [Fase 1 — Gerenciador](EMULATOR_MANAGER.md).

## 🧭 Camadas de API

| Camada | Onde executa | Uso |
|---|---|---|
| Dashboard | `webapp.py`, host/contêiner central | O navegador consulta estado e solicita ações por endpoints `/api/*`. |
| Agente de perfil | `console_agent.py`, um por ambiente | O dashboard consulta/controla o agente via rede interna usando token próprio. |
| CLI | `emustack.py` | Ferramenta local para diagnóstico, listagem, launch e manutenção. |

As rotas e os campos podem mudar entre versões. Consulte o código da mesma revisão antes de integrar outras ferramentas.

## 🌐 Dashboard — leitura

Todos os endpoints de dashboard abaixo usam JSON quando indicados. Em ambiente Compose, os endpoints operacionais estão atrás da validação de IP de origem do dashboard. A porta de host fica em `127.0.0.1:8765`.

| Método e caminho | Resposta/uso | Observações |
|---|---|---|
| `GET /api/health` | Sumário de saúde do núcleo. | Origem não confiável recebe somente `{"healthy": true}`; isso não é uma auditoria detalhada. |
| `GET /api/environments` | Lista os ambientes, status online e política de storage. | Dados operacionais; requer origem confiável. |
| `GET /api/console-systems` | Lista sistemas originais e estratégias/pré-requisitos resolvidos. | Pré-requisito encontrado não comprova boot visual. |
| `GET /api/catalog` | Catálogo de launchers com status/resumo runtime. | `binary_found` não significa jogo compatível. |
| `GET /api/processes` | Sessões/processos visíveis ao dashboard e contador de ativos. | No modo isolado, agrega status dos agentes. |
| `GET /api/processes/<environment-id>/<session-id>/log` | Log de uma sessão do agente. | No modo isolado, o ID de sessão deve obedecer ao formato aceito pelo agente. |
| `GET /api/games` | Biblioteca encontrada e limite da varredura. | Não copia nem valida completamente os arquivos. |
| `GET /api/sources` | Catálogo `game-sources.json`. | Links são pontos de descoberta, não certificado de licença. |
| `GET /api/report` | Relatório de instalação, se estiver presente. | Se não houver relatório, retorna `available: false`. |
| `GET /api/docs` | Documentação Markdown carregada pelo painel. | Não usar para compartilhar inadvertidamente documentos com dados locais. |
| `GET /` e arquivos estáticos | HTML, JS, CSS, ícone e assets da UI. | Paths estáticos são confinados à pasta web. |

### Contratos de leitura

Exemplos ilustrativos de respostas:

```json
{
  "version": "0.7.1",
  "policy": "DENY_CROSS_ENVIRONMENT_STORAGE",
  "count": 20,
  "online": 20,
  "environments": []
}
```

O array acima foi abreviado: a API retorna os registros de ambiente do runtime consultado. Os números representam somente um exemplo de formato, **não o estado atual de uma máquina**.

```json
{
  "available": false,
  "message": "Relatório de build/instalação não encontrado; faça o build da imagem."
}
```

Campos internos de ambientes, processos e catálogo podem evoluir. Consumidores devem tratar campos ausentes/novos com tolerância e nunca assumir que um perfil listado tem binário.

## ✍️ Dashboard — ações mutáveis

A UI envia um objeto JSON com headers de requisição da interface local. As ações não devem ser expostas como uma API genérica a clientes externos.

### Headers/validação

- `Host` precisa identificar a interface local no formato esperado (normalmente `127.0.0.1:8765`).
- Se `Origin` estiver presente, seu `netloc` precisa corresponder ao `Host`.
- `X-EmuStack-Request: 1` indica uma chamada reconhecida pela interface.
- A origem TCP precisa ser confiável. Headers personalizados não provam identidade de rede; os agentes são barrados pelo IP de origem.
- O corpo precisa ser JSON válido, um objeto e estar dentro do limite de tamanho configurado no código.

Esses checks não autorizam publicar a aplicação remotamente. Não contorne recusas removendo o filtro de origem.

### `POST /api/launch`

Inicia um launcher cadastrado para um arquivo de jogo opcional.

```json
{
  "emulator": "rpcs3",
  "game": "PastaOuArquivoDoJogo"
}
```

`emulator` deve ser um ID cadastrado. `game` é um caminho relativo seguro dentro de `games/` do perfil no modo isolado; use string vazia ou omita quando o launcher deve abrir sua própria interface. O path é validado e o agente não aceita argumento arbitrário do navegador. A chamada é recusada quando o ambiente/runner não existe, está offline, o perfil está bloqueado, falta display ou os parâmetros são inválidos.

### `POST /api/console-systems/launch`

Pede para abrir o emulador associado (`action: "open"`) ou tentar o sistema/menu (`action: "boot"`).

```json
{
  "system": "ps3-xmb",
  "action": "boot"
}
```

O exemplo ilustra a forma do payload; use somente IDs realmente definidos em `console-systems.json` para a revisão instalada. `boot` só é aceito quando o perfil resolve `can_boot_original` como verdadeiro e os pré-requisitos declarados estão presentes. Erros de pré-requisito são retornados como erro de domínio; a presença dos arquivos não é prova de boot real.

### `POST /api/processes/stop`

No modo Compose isolado, o corpo associa a sessão ao seu ambiente:

```json
{
  "environment_id": "rpcs3",
  "session_id": "0123456789abcdef0123456789abcdef"
}
```

Use o ID retornado pela API para a sessão real — o identificador acima é fictício. Um ID válido de formato que não existe ainda pode produzir 404; sessão já terminada pode produzir 409. Não mate processos manualmente como primeira opção quando a UI puder encerrar a sessão e registrar o resultado.

## 🔑 API dos agentes — somente rede interna

O dashboard conecta-se a `env-<id>:<porta>` na rede privada do agente. Essas rotas não devem ser acessadas a partir do navegador nem publicadas no host.

| Método/caminho interno | Uso | Autorização |
|---|---|---|
| `GET /health` | Estado do agente, perfil e disponibilidade do binário. | Health é a exceção sem token; não o trate como endpoint de auditoria pública. |
| `GET /games` | Biblioteca do perfil. | `X-EmuStack-Agent-Token` individual. |
| `GET /processes` | Sessões do agente. | Token individual. |
| `GET /processes/<session-id>/log` | Log de sessão. | Token individual. |
| `GET /system-status?system=<id>` | Estado resolvido do sistema atribuído ao perfil. | Token individual. |
| `POST /launch` | Solicita iniciar o jogo permitido. | Token individual + validação de payload/path. |
| `POST /console-system` | Solicita ação `boot` ou `open`. | Token individual + associação do sistema ao ambiente. |
| `POST /processes/stop` | Encerra uma sessão desse agente. | Token individual + ID de sessão validado. |

O header de agente é um segredo por perfil, emitido por `scripts/host-setup.sh` e armazenado em `.env`. O agente compara o valor em tempo constante e rejeita chamadas não autenticadas. Nunca use um token compartilhado nem inclua o valor em exemplos, logs ou documentação.

## 📟 CLI (`emustack.py`)

Rode a partir da raiz do checkout. Para a ajuda exata da revisão local, use `python3 emustack.py --help` e o `--help` de cada subcomando.

| Comando | Finalidade |
|---|---|
| `python3 emustack.py list` | Lista projetos e detecta launchers disponíveis. |
| `python3 emustack.py doctor` | Diagnóstico de diretórios, sessão gráfica, Vulkan e Wine. |
| `python3 emustack.py launch <id> [game]` | Inicia um emulador cadastrado, com jogo opcional conforme o perfil. |
| `python3 emustack.py catalog` | Mostra localização/contagem do catálogo. |
| `python3 emustack.py install-report` | Mostra resultado de downloads/builds upstream. |
| `python3 emustack.py export-lock` | Exporta lock a partir dos assets upstream instalados — use no fluxo controlado de atualização. |
| `python3 emustack.py boot-system <system-id>` | Tenta o caminho de sistema/menu nativo se a estratégia oferecer suporte. |
| `python3 emustack.py web --host 127.0.0.1 --port 8765` | Sobe o dashboard. O padrão seguro de bind é loopback. |

Use a API do dashboard para a UI normal. A CLI é uma ferramenta local confiável: não passe paths, flags ou arquivos provenientes de fontes não confiáveis sem conferir. O subcomando de launch pode aceitar argumentos adicionais da linha de comando; a API web não expõe essa liberdade ao navegador.

## 💾 CLI de storage

`scripts/manage-storage.py` possui estes comandos:

```bash
python3 scripts/manage-storage.py init
python3 scripts/manage-storage.py inspect
python3 scripts/manage-storage.py inspect rpcs3
python3 scripts/manage-storage.py backup rpcs3
python3 scripts/manage-storage.py restore rpcs3 backups/rpcs3/ARQUIVO.tar.gz
python3 scripts/manage-storage.py create-disk xemu --size 8G --format qcow2
```

`init`, `inspect` e comandos equivalentes aceitam o ID opcional quando aplicável; `backup`/ `restore` e `create-disk` exigem um perfil. A restauração usa verificação e rollback, e o disco criado é vazio. Use `--help` para ver opções como `--output`, `--allow-running` (opção arriscada) e formatos suportados (`qcow2`, `raw`).

## ⚠️ Códigos HTTP e tratamento recomendado

Os códigos refletem a camada que recusou a ação. Use o texto `error`, o estado retornado e os logs para diagnóstico; não trate todos os 4xx como problema de rede.

| Código comum | Interpretação típica |
|---|---|
| `200` | Consulta concluída ou operação respondida normalmente. |
| `202` | Sessão iniciou/continua em transição/encerramento. |
| `400` | JSON, ID, payload, argumento ou caminho inválido. |
| `403` | Origem não confiável ou token de agente ausente/incorreto. Para uma tentativa originada do agente, a recusa é esperada. |
| `404` | Rota, ambiente, sistema ou sessão não reconhecido. |
| `409` | Estado atual não permite a ação: runner ausente, boot não suportado, pré-requisitos não atendidos ou sessão concluída. |
| `413` | Corpo ausente ou acima do limite de tamanho. |
| `429` | Limite de ambientes ativos atingido. |
| `502` | Launcher terminou imediatamente durante a inicialização no modo local; consulte o log. |
| `503` | Agente/serviço indisponível ou falha ao consultar o upstream interno. |

A lista é ilustrativa, não enumeração exaustiva nem compromisso de compatibilidade da API entre versões.
