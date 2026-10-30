# Solução de problemas — EmuStack 0.7.1

> **EMUSTACK // GAMING LAB** · [README](../README.md) · [Instalação](INSTALLATION.md) · [Guia do usuário](USER_GUIDE.md) · [Matriz de emuladores](EMULATOR_MATRIX.md) · [Segurança](SECURITY.md) · [Identidade visual](IDENTIDADE-VISUAL.md)

## O dashboard não abre

```bash
docker compose ps
docker compose logs --tail=200 dashboard
```

A porta do host é `127.0.0.1:8765`. Confirme o token em `.env` (não o publique), que o `host-setup.sh` foi executado e que o dashboard está saudável. Se você especificou `-f compose.yaml` manualmente e usa GUI, inclua também `-f compose.override.yaml` quando esse arquivo existir.

## Agentes offline

```bash
docker compose logs --tail=200 env-rpcs3
docker compose ps env-rpcs3
```

Confirme que o `.env` contém `EMUSTACK_AGENT_TOKEN_RPCS3` e as outras 19 variáveis `EMUSTACK_AGENT_TOKEN_<ID>`, cada uma com um valor hexadecimal distinto. Depois de mudar tokens, recrie dashboard e agente afetados: `docker compose up -d --force-recreate dashboard env-rpcs3`. O `host-setup.sh` gera segredos se estiverem ausentes e preserva os existentes; nunca publique o `.env`.

## Emulador não encontrado

Veja a aba de relatório e os logs do build. “Agente online” indica que o pequeno servidor de controle responde, não que o emulador esteja instalado. O relatório upstream pode indicar ativo indisponível, falha de formato ou build falho. Coloque override confiável em `data/environments/<id>/emulators/` somente quando o nome de executável for reconhecido pelo catálogo.

## Jogo não aparece

Coloque-o em `data/environments/<id>/games/` no perfil certo e atualize o dashboard. A varredura ignora arquivos ocultos, symlinks e extensões não reconhecidas e limita a biblioteca global a 3.000 resultados. Não há busca recursiva em diretórios compartilhados antigos.

## Launch retorna conflito

- O agente está offline ou não tem binário.
- O emulador não tem runner compatível ou o perfil está bloqueado.
- O caminho não está na raiz daquele ambiente, contém `..`, é symlink ou não é arquivo regular.
- O limite global/per-ambiente de sessões foi atingido.
- Para jogos gráficos, `DISPLAY` pode não estar configurado dentro do agente.

Abra o log na seção **Sessões** ou consulte `data/environments/<id>/home/.local/state/emustack/logs/`.

## Tela preta, falha de GUI ou áudio

1. Execute `host-setup.sh` numa sessão com X11/XWayland e Xauthority legível.
2. Confira se `compose.override.yaml` foi gerado e se o socket PulseAudio/PipeWire é acessível no host.
3. Confira o log do ambiente e a versão do driver dentro do contêiner.
4. Para NVIDIA, verifique o NVIDIA Container Toolkit e use `USE_NVIDIA=1 ./scripts/build-and-audit.sh`.
5. Teste primeiro sem afirmar boot de sistema completo. Uma tela preta pode ser limitação do emulador, firmware inadequado, incompatibilidade de renderização ou driver.

## Boot original indisponível

A detecção precisa de binário, estratégia suportada, pré-requisitos e DISPLAY. PS3 precisa de firmware instalado; PS2 precisa de BIOS válida selecionada; Wii/Wii U precisam de System Menu/NAND ou MLC; xemu precisa de configuração e dados de sistema/HDD; a simples existência do TOML não habilita o botão de boot original, porque o dashboard do HDD não é verificado automaticamente. O boot não é oferecido para sistemas cujo emulador não tem caminho comprovado. Consulte `ORIGINAL_SYSTEM_UI.md`.

## Migrar uma instalação antiga

A 0.7.1 não monta as pastas compartilhadas `data/games/`, `data/bios/`, `data/saves/` ou `data/home/`. Copie os dados manualmente para o ambiente correto após backup. Não apague os dados originais até confirmar o resultado.

## POST de controle recusado com HTTP 403

No modo Docker, a API de controle aceita apenas loopback e gateways explicitamente allowlisted. Se o navegador local for recusado, confira o port publishing `127.0.0.1:8765` e se o IP de origem aparece entre os gateways configurados. Não resolva removendo a checagem ou liberando as redes dos agentes.
