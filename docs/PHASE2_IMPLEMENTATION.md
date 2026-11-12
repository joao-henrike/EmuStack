# Fase 2 — Experiência de console (Docker-first, KISS)

**Branch de implementação:** fix/dashboard-degraded-startup. Este documento registra o código da experiência de interface, que pode ser testado parcialmente sem hardware físico. **Não declara boot de console, jogo, GPU ou controle físico já comprovados.**

## Escopo implementado

| Requisito | Implementação | Limite |
|---|---|---|
| Modo TV | Botão no topo da UI, alvos/fontes ampliados e foco visível | Adapta o dashboard HTML; não emula um menu original |
| Navegação por teclado | Setas percorrem comandos visíveis no modo TV e Enter usa o comportamento nativo | Inputs e selects mantêm comportamento normal |
| Controle no navegador | Gamepad API com D-pad/analógico, A/B e Start/Options | Depende do browser/dispositivo; não utiliza /dev/input |
| Tela cheia | Fullscreen API mediante clique explícito e aviso se recusada | Depende de permissão; não é restaurada automaticamente |
| Ajustes visuais | Contraste reforçado e redução de movimento, inclusive a preferência do sistema | Não modifica GPU, Vulkan, driver, resolução ou opções de emulador |
| Centro de sessões | Aba com contadores, filtros, botão atualizar, logs e parada de sessão | Reutiliza endpoints existentes; não observa processos externos |

A configuração é persistida no navegador sob a chave **emustack:experience:v1**, com validação de tipos booleanos. Parâmetros inesperados são descartados. Falha de armazenamento local não impede uso da interface. O Gamepad API é consultado somente em modo TV, quando habilitado e com a página visível. Não foram acrescentados mounts, serviços, permissões de host ou endpoints privilegiados.

## Arquivos e responsabilidade

- **web/experience.js**: preferências, foco e controle, com funções puras testáveis.
- **web/index.html**: controles de TV, painel de ajustes e seção dedicada a sessões.
- **web/app.js**: renderização de sessões e reaproveitamento das rotas já existentes.
- **web/app.css**: apresentação de TV, acessibilidade e preferências visuais.
- **tests/test_experience.js**: cenários de preferências inválidas, Gamepad API, bordas de foco e contrato HTML.
- **scripts/validate-project.sh** e **.github/workflows/ci.yml**: validação automática.

## Aceitação automática

A CI deve executar os testes Node (incluindo o novo módulo), sintaxe JavaScript, testes Python pré-existentes, validação de lock, manifestos Compose, build e runtime acceptance do ambiente isolado. Essas verificações **não** comprovam que um controle real funciona, nem que jogos/menus renderizam com GPU física.

## Aceitação manual posterior no Debian

1. Abrir a interface apenas em http://127.0.0.1:8765 e alternar modo TV.
2. Navegar por setas/Enter e por um controle real num navegador que ofereça Gamepad API; verificar A, B, Start, diálogos e campos de entrada.
3. Testar tela cheia, sua saída, contrastes, movimento reduzido e dimensões pequenas/grandes de janela.
4. Iniciar uma sessão autorizada de teste em um perfil com runner, atualizar a aba Sessões e observar processos, filtros, logs e encerramento.
5. Repetir com agente indisponível, sem display, sem controle ou com fullscreen negado, para confirmar degradação segura.
6. Guardar SHA do commit, versão do navegador, OS/display, diagnósticos e resultados sem publicar tokens ou conteúdo proprietário.

## Fora de escopo

- Imitação de XMB, Home Menu ou Xbox Dashboard em HTML; menus originais permanecem dependentes do upstream e de arquivos legais do operador.
- Instalação/ajuste de drivers, GPU, emuladores, BIOS, firmware ou jogos pelo painel.
- Socket Docker, dispositivos locais compartilhados com dashboard ou downloads de ROMs.
- Afirmação de compatibilidade sem execução gráfica e teste específico.

A fundação da **Fase 1** continua definida em [PHASE1_IMPLEMENTATION.md](PHASE1_IMPLEMENTATION.md), com aceitação do host em [LOCAL_ACCEPTANCE.md](LOCAL_ACCEPTANCE.md).
