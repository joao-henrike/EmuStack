# 🧰 Solução de problemas

Use a seção que corresponde ao sintoma. Preserve a saída útil e evite apagar dados, regenerar tokens ou reconstruir tudo antes de verificar a causa.

## 🌐 O dashboard não abre

Comece incluindo contêineres parados na inspeção: `docker compose ps` normalmente mostra apenas os ativos.

```bash
docker compose ps -a
docker compose logs --tail=200 dashboard
docker compose logs --tail=200 dashboard-proxy
docker compose logs --tail=100 env-rpcs3
CID="$(docker compose ps -aq dashboard-proxy)"
if [ -n "$CID" ]; then
  docker inspect "$CID" --format 'state={{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}} error={{.State.Error}}'
fi
curl -i --max-time 5 http://127.0.0.1:8765/api/health
```

Use os mesmos arquivos `-f` e o mesmo projeto Compose usados na inicialização. A porta pertence a `dashboard-proxy`, não ao serviço `dashboard`: o dashboard fica somente em redes internas e não publica a porta diretamente. Um contêiner em estado `created` ou `exited` não tem porta publicada ativa; `HostConfig.PortBindings` sozinho mostra apenas a configuração pretendida. Confirme também `NetworkSettings.Ports` no contêiner `dashboard-proxy`.

O dashboard é iniciado depois que os contêineres dos agentes começam, mas não espera que todos passem no healthcheck. Assim, a interface pode abrir em modo degradado e mostrar agentes offline; a aceitação completa continua exigindo os 20 agentes saudáveis. O proxy aguarda o dashboard iniciar e publica a interface somente no loopback.

**Não acrescente `compose.nvidia.yaml` incondicionalmente.** Esse overlay solicita `gpus: all` para todos os 20 agentes e depende do NVIDIA Container Toolkit no host. Para uma execução sem GPU NVIDIA, use apenas `compose.yaml` e, quando existir, `compose.override.yaml`. Para habilitar NVIDIA, configure o toolkit e use `USE_NVIDIA=1` nos scripts documentados.

Confirme também que `host-setup.sh` foi executado e que você está acessando a máquina local. O endereço publicado pelo proxy é `127.0.0.1:8765`; o projeto não oferece acesso remoto/LAN suportado. Se subiu a stack manualmente e precisa de GUI/áudio, inclua `-f compose.override.yaml` quando o arquivo existir. O proxy está em `read_only: true`; todos os diretórios temporários do Nginx (client body, proxy, FastCGI, uWSGI e SCGI) precisam usar `/tmp`, fornecido pelo `tmpfs`. Se o log mencionar `/var/cache/nginx`, confira as diretivas `*_temp_path` de `proxy/nginx.conf`.

## 🧩 Agente offline ou token rejeitado

```bash
docker compose ps env-rpcs3
docker compose logs --tail=200 env-rpcs3
docker compose logs --tail=200 dashboard
```

Troque o nome pelo ID afetado. Confira o `.env` local: cada um dos 20 `EMUSTACK_AGENT_TOKEN_<ID>` deve ter um valor distinto. Nunca publique o arquivo. Se rotacionar token, recrie dashboard e agente correspondentes usando a mesma configuração Compose. Não substitua por um token compartilhado.

## 📦 Emulador não encontrado

“Agente saudável” só informa que o controlador responde. Consulte `install-report.json` e `release-lock.json`. O build pode indicar asset indisponível, formato incompatível, erro de download ou build falho. Em particular, as entradas `skip-upstream` não representam binários instalados pelo lock atual. Não baixe executáveis de fontes aleatórias para preencher o catálogo.

Um override em `data/environments/<id>/emulators/` só será útil quando o binário for reconhecido pelo catálogo e compatível com o runner configurado.

## 🎮 Jogo ausente na biblioteca

1. Copie o arquivo para `data/environments/<id>/games/` do sistema correto.
2. Confira se é arquivo regular, não symlink e não oculto.
3. Confirme que a extensão está entre as reconhecidas pelo scanner.
4. Atualize a página e selecione o ID certo.
5. Consulte logs e limites da biblioteca se houver muitos arquivos.

A busca não transforma formatos, não verifica integridade completa e não prova compatibilidade.

## ⛔ Lançamento rejeitado / conflito

Causas possíveis:
- agente offline ou binário ausente;
- perfil intencionalmente bloqueado/não suportado;
- path absoluto, travessia `..`, symlink ou arquivo fora da raiz;
- extensão/ID não reconhecido;
- limite de sessões atingido;
- ausência de DISPLAY ou problema de renderização;
- BIOS/firmware/pré-requisitos ausentes.

Confira **Sessões**, o relatório do perfil e:
```bash
docker compose logs --tail=200 env-pcsx2
```

## 🖥️ Tela preta ou GUI não inicia

- Rode `host-setup.sh` dentro da sessão gráfica correta.
- Confirme `DISPLAY`, XWayland/Xauthority e que `compose.override.yaml` foi gerado quando esperado.
- Revise os mounts e as permissões; não flexibilize permissões globais do host à toa.
- Confira logs e versão do emulador.
- Teste primeiro se a janela do próprio emulador abre; só depois avalie sistema/menu/jogo.
- Uma tela preta pode indicar incompatibilidade do runner, falta de firmware, renderer, drivers ou parâmetros de launch incorretos.

Wayland puro não implica que qualquer janela X11 funcionará. A compatibilidade depende do compositor, XWayland e da configuração real.

## 🔊 Sem áudio

Verifique o socket Pulse compatível e o override gerado na sessão em que o dashboard roda. Faça o probe:
```bash
EMUSTACK_REQUIRE_AUDIO=1 ./scripts/runtime-acceptance.sh
```

Esse teste confirma conectividade do caminho testado, não volume nem áudio de cada jogo.

## 🎨 Vulkan/GPU mostra llvmpipe ou falha

`llvmpipe`/`lavapipe` são renderizadores de software no contexto do probe. Para NVIDIA:
```bash
nvidia-smi
USE_NVIDIA=1 ./scripts/build-and-audit.sh
USE_NVIDIA=1 EMUSTACK_REQUIRE_VULKAN=1 EMUSTACK_REQUIRE_GPU=1 ./scripts/runtime-acceptance.sh
```

Confirme o driver do host e NVIDIA Container Toolkit. Um probe GPU aprovado não garante que o emulador selecione o backend correto ou que todos os títulos rodem.

## 🎮 Controle não aparece

Nada é mapeado por padrão. Confirme o node real do controle e atribua apenas um dispositivo a um ambiente:
```bash
EMUSTACK_INPUT_DEVICE=/dev/input/js0 EMUSTACK_INPUT_ENV=rpcs3 ./scripts/host-setup.sh
EMUSTACK_REQUIRE_INPUT=1 ./scripts/runtime-acceptance.sh
```

Não selecione teclado/mouse. A aceitação confirma presença/acesso, não substitui a configuração de botões de cada emulador.

## 🛡️ Requisição do agente recebe HTTP 403

Para tentativas provenientes do IP do agente, HTTP 403 é o resultado esperado nas rotas protegidas. A origem confiável é o IP TCP configurado, não `Host`, `Origin` ou um header customizado. Não desabilite o filtro para resolver esta resposta.

Se o navegador local for bloqueado, revise a publicação `127.0.0.1:8765`, a rede que realmente encaminha o tráfego, gateways e allowlist. Se houver sobreposição com VPN/LAN, replaneje os subnets e atualize IPAM/allowlist em conjunto.

## 🌐 Conflito de subnets ou rede não sobe

O Compose usa o intervalo padrão `172.28.0.0/16` subdividido para 20 perfis. Se sua rede existente ou VPN se sobrepõe, escolha uma faixa sem conflito. Modifique subnets, gateway, IPs estáticos, allowlist e checks de CI/testes em conjunto; uma mudança parcial quebra a identidade confiável dos clientes.

## 🧱 Build falha ou pacote APT não tem candidato

Guarde o final do log do build, o erro do Dockerfile e o relatório. A resolução de pacote precisa encontrar um candidato instalável real no APT, não apenas metadata antiga. Confira conectividade, arquitetura e disponibilidade do pacote na distribuição/repositório utilizados. Não contorne o erro instalando pacote de origem aleatória.

## 🔐 Lock inválido / hash não corresponde

Execute:
```bash
python3 scripts/check-release-lock.py release-lock.json --require-strict --require-pins
```

Confira o arquivo upstream, tag, asset, URL e SHA-256. Um hash divergente pode representar asset alterado, resposta inesperada ou erro de integração. Não atualize o hash automaticamente sem rever a origem e o artefato baixado.

## 🖥️ Boot original indisponível

Confira a matriz e os pré-requisitos. PS3 precisa firmware; PS2/PS1 dependem de BIOS válida e configuração; Wii/Wii U precisam de NAND/System Menu ou MLC/arquivos do sistema; xemu precisa MCPX, BIOS e HDD configurados. Para PSP, VSH/XMB segue experimental. PS5, PS4 e outras rotas sem boot integral declarado não devem ser tratadas como suportadas só porque o perfil está no catálogo.

## 💾 Backup/restore falha

- Pare o agente antes de copiar.
- Confirme que o ID é um dos 20 IDs de `environments.json`.
- Verifique espaço livre e a integridade do arquivo de backup.
- Não edite o manifesto/hash dentro do arquivo para “consertar” o restore.
- Preserve a pasta rollback até confirmar a recuperação.
- Não use symlink para redirecionar a raiz de um perfil.

Leia [Guia do usuário](USER_GUIDE.md#armazenamento-backup-e-restauração).

## 🆘 O que anexar ao relatório

Inclua commit, sistema operacional/arquitetura, comando executado, código de saída, trecho de log relevante e os arquivos `install-report.json`/ `runtime-acceptance.json` **depois de sanitizar** paths e dados locais. Nunca inclua `.env`, BIOS/firmware, jogos, dumps de disco, saves ou chaves.
