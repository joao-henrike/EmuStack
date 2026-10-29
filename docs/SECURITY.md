# 🛡️ Modelo de segurança — EmuStack 0.7.1

## 🎯 Objetivo

Reduzir a exposição desnecessária entre dashboard, agentes e dados persistentes dos perfis. A configuração é voltada a uso **local e individual**. Não é uma plataforma multiusuário nem uma sandbox de alta garantia para executar arquivos deliberadamente maliciosos.

## ✅ Defaults de segurança relevantes

- Dashboard publicado apenas em `127.0.0.1:8765`; não projetado para LAN/Internet ou reverse proxy.
- Dashboard restringe endpoints operacionais por origem TCP confiável: loopback/gateways allowlisted, conforme o modo de rede.
- 20 bridges internas exclusivas com IPAM previsível; o gateway é `.1`, o agente `.2` e dashboard `.3` em cada subnet.
- Allowlist de IP contém gateways previstos, não os IPs dos agentes. Headers HTTP forjados não substituem a verificação da origem TCP.
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

Porta de host vinculada a loopback não é o único controle: as rotas do dashboard também verificam a origem TCP dos clientes. A topologia esperada coloca dashboard e agentes nas redes internas para coordenação. O teste de runtime tenta POSTs de estado e acessos de metadados a partir dos 20 agentes; essas tentativas devem receber recusa (normalmente HTTP 403), enquanto o health não confiável deve revelar somente informação mínima.

Não remova a allowlist para contornar erro. Se a rede local/VPN se sobrepõe à faixa padrão `172.28.0.0/16`, escolha uma faixa apropriada e atualize em conjunto IPAM, gateways, endereços e allowlist. Não publique a porta via proxy nem encaminhe-a no roteador.

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
