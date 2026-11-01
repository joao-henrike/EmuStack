# 🛡️ Modelo de segurança — EmuStack 0.7.1

**Segurança da Fase 1:** build não tem socket Docker, capabilities nem escrita em jogos, saves ou BIOS. Pacotes versionados são conferidos por SHA-256 e symlinks bloqueados; rollback verifica recursos antigos. `sync-deps` modifica apenas origens Git pinadas dentro de mounts RW explícitos. Acesso ao daemon Docker no host continua altamente privilegiado. [Detalhes](PHASE1_IMPLEMENTATION.md).

## Isolamento de toolchain — Docker-first

Compilações e inspeções de perfis usam `bash scripts/phase1.sh`, que não compartilha o Docker socket com os containers, monta o checkout somente leitura e mantém apenas `data/` como pasta persistente gravável. Testes/inspeções são sem rede; a rede da compilação é explicitamente necessária para alguns upstreams. Essa abordagem **não garante ausência de risco**: código upstream ainda é executado, e quem pode usar o Docker daemon no host tem privilégios elevados. Mantenha o dashboard longe do daemon. Leia [arquitetura Docker-first](DOCKER_FIRST_ARCHITECTURE.md).

## 🎯 Objetivo

Reduzir a exposição desnecessária entre dashboard, agentes e dados persistentes dos perfis. A configuração é voltada a uso **local e individual**. Não é uma plataforma multiusuário nem uma sandbox de alta garantia para executar arquivos deliberadamente maliciosos.

## ✅ Defaults de segurança relevantes

- Apenas `dashboard-proxy` publica `127.0.0.1:8765`. O serviço `dashboard` não publica portas e permanece nas redes internas; não há suporte a publicação LAN/Internet nem a proxies externos.
- Dashboard restringe endpoints operacionais por origem TCP confiável: gateways das 20 bridges de agentes e o IP fixo do proxy na bridge backend privada. Headers `X-Forwarded-For` não participam da decisão.
- 20 bridges internas exclusivas com IPAM previsível; o gateway é `.1`, o agente `.2` e dashboard `.3` em cada subnet. Uma 21ª bridge interna conecta somente dashboard (`172.29.0.3`) e proxy (`172.29.0.2`).
- Allowlist de IP contém gateways previstos e o IP fixo do proxy, nunca os IPs dos agentes. Headers HTTP forjados não substituem a verificação da origem TCP.
- Cada agente possui token distinto de 256 bits gerado no setup, em `.env` com permissões restritas.
- Nenhum socket Docker é montado no dashboard ou nos agentes.
- Dashboard não monta pastas persistentes de jogos/BIOS/saves/HOME dos agentes.
- Mounts de jogos/BIOS read-only; estado gravável limitado a HOME/saves do ambiente correspondente.
- Contêineres de agente usam, conforme manifestos, filesystem root read-only, `cap_drop: ALL`, `no-new-privileges`, `tmpfs` e limites de recursos.
- APIs validam ID e parâmetros, rejeitam paths inseguros e não aceitam shell/binário arbitrário via requisição.
- Nenhum input é mapeado por padrão. GUI/áudio/GPU/controle precisam de concessão local explícita.

## 🧭 Modelo de ameaça

| Ativo | Risco | Mitigação presente | Limite residual |
|---|---|---|---|
| Dados de cada console | Outro agente ler/gravar o estado | Mounts exclusivos, política de dados, rejeição de symlinks | Erros no host/configuração Docker ainda podem invalidar o limite. |
| API do dashboard | Agente comprometido chamar endpoints operacionais | Allowlist TCP + tokens individuais + validação de campos | Dashboard é o orquestrador e possui credenciais de vários agentes. |
| Host/desktop | Emulador acessar recursos expostos | Integrações explícitas e mínimas | X11/GPU/áudio/input ampliam a superfície; não use com código não confiável. |
| Execução de emuladores | Bug/vulnerabilidade no programa | Contêiner endurecido e limites | Docker compartilha kernel e não elimina exploits. |
| Jogos/firmware | Arquivos não confiáveis, maliciosos ou ilegais | Não há downloader/distribuição de tais arquivos | Usuário continua responsável por validar origem e direitos. |
| Segredos/logs | Token ou metadados vazados | `.env` privado; relatórios localmente armazenados | Usuário pode compartilhar artefatos sem sanitização. |

## 🌐 Dashboard, redes e allowlist

Porta de host vinculada a loopback não é o único controle: as rotas do dashboard também verificam a origem TCP dos clientes. O dashboard permanece somente nas redes internas. Um proxy Nginx sem privilégios, com filesystem read-only e configuração fixa, compartilha uma bridge interna dedicada com o dashboard e uma bridge não interna usada apenas para a publicação da porta. Essa segunda bridge dá ao proxy um caminho de gateway; o dashboard não recebe egress por ela. O proxy não compartilha redes com agentes, não é um forward proxy e encaminha somente para `dashboard:8765`. O teste de runtime tenta POSTs de estado e acessos de metadados a partir dos 20 agentes; essas tentativas devem receber recusa (normalmente HTTP 403), enquanto o health não confiável deve revelar somente informação mínima.

Não remova a allowlist para contornar erro. Se a rede local/VPN se sobrepõe às faixas padrão `172.28.0.0/16` ou `172.29.0.0/24`, escolha faixas apropriadas e atualize em conjunto IPAM, gateways, endereços e allowlist. Não exponha o proxy por outro IP, reverse proxy externo ou encaminhamento no roteador.

## 🔑 Tokens e segredos

- Nunca versione, cole em issues, envie por chat público ou inclua em capturas o conteúdo do `.env`.
- Não use um único token em vários agentes.
- Ao rotacionar tokens, recrie os serviços correspondentes e valide dashboard-agente.
- Não compartilhe `compose.override.yaml` sem revisar: pode conter paths de socket/desktop locais.
- Mantenha jogos, BIOS, firmware, dumps, saves e chaves fora do repositório.
- Revise `data/host-capabilities.json`, `install-report.json` e `data/runtime-acceptance.json` antes de anexar.

## 🧱 Limites técnicos — leia antes de confiar

1. **Contêiner não é VM:** os agentes compartilham o kernel do host e a imagem comum de programas.
2. **Dashboard privilegiado logicamente:** ele coordena todos os agentes; um dashboard comprometido teria poder para solicitar ações válidas usando suas credenciais.
3. **Recursos do host:** GPU, display, áudio e controladores concedidos ficam expostos ao processo do emulador, conforme os mounts/permissões.
4. **Sem garantia de segurança absoluta:** as proteções reduzem caminhos de ataque, não substituem patches, isolamento dedicado, monitoramento e revisão independente.
5. **Sem garantia legal/técnica dos arquivos:** detecção de arquivo não comprova autenticidade, licença ou compatibilidade.
6. **Sem exposição remota suportada:** faltam controles adicionais normalmente exigidos para publicação remota, como autenticação externa robusta, CSRF/revisão de proxy, limitação de taxa e análise específica do deployment.

Para código ou arquivos de terceiros dos quais você não confia, prefira uma VM/host descartável com credenciais e dados separados e sem dispositivos do desktop mapeados.

## 🧰 Ferramentas de host e builds de upstream

`scripts/emulator-manager.py` opera no host como usuário normal, sem expor ações de instalar/desinstalar na API. Arquivos importados precisam ter nome permitido pelo catálogo e hash SHA-256 explícito; checksum não é assinatura de fornecedor. O gerenciador rejeita symlinks nos destinos e mantém cópias antigas fora dos mounts dos agentes. Builds de KytyPS5, shadPS4, PPSSPP, melonDS e bsnes **executam código de terceiros no host** somente após sinalizador de aceite: revide a origem e prefira VM descartável para código não confiável. Nunca execute como root. Testes de fronteira Docker não certificam segurança de um build executado fora do contêiner.

## 🧪 Verificação operacional

```bash
./scripts/validate-project.sh
docker compose -f compose.yaml config --quiet
./scripts/build-and-audit.sh
./scripts/runtime-acceptance.sh
```

A aceitação deve verificar IPAM, allowlist, mounts, hardening e tentativa de acesso a partir de cada agente. Guarde falhas e corrija a causa. Não alegue “auditado” com base somente em testes unitários.

## 🚨 Reportar um problema

Não publique segredos, arquivos proprietários nem detalhes exploráveis sensíveis em uma issue pública. Use o mecanismo privado de reporte de vulnerabilidades do GitHub se estiver habilitado para o repositório; caso contrário, solicite um canal privado ao mantenedor antes de divulgar detalhes. Informe versão/commit, impacto, condições de reprodução minimizadas e evidência sanitizada.
