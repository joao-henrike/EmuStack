# 🧭 Central da documentação EmuStack

Bem-vindo à central de documentação do EmuStack. Os guias são organizados por tarefa e por área técnica; os links levam às páginas que explicam comandos, limitações e evidências.

> [!NOTE]
> **Regra de leitura:** perfil no catálogo, asset fixado, processo em execução, jogo compatível e boot do menu original são estados diferentes. Sempre consulte a matriz e o relatório do host antes de concluir que um sistema funciona.

## 🚀 Quero começar

| Objetivo | Leia primeiro | Depois |
|---|---|---|
| Instalar do zero | [Instalação](INSTALLATION.md) | [Configuração](CONFIGURATION.md), [Aceitação local](LOCAL_ACCEPTANCE.md) |
| Abrir o painel | [Guia do usuário](USER_GUIDE.md) | [Solução de problemas](TROUBLESHOOTING.md) |
| Saber o que cada console suporta | [Matriz de emuladores](EMULATOR_MATRIX.md) | [Menus originais](ORIGINAL_SYSTEM_UI.md) |
| Usar jogos, BIOS e saves próprios | [Guia do usuário](USER_GUIDE.md) | [Fontes e direitos](GAME_SOURCES.md) |
| Fazer backup ou recuperar dados | [Guia do usuário](USER_GUIDE.md#armazenamento-backup-e-restauração) | [Ambientes isolados](ISOLATED_ENVIRONMENTS.md) |
| Testar GUI, áudio, Vulkan, GPU ou controle | [Aceitação local](LOCAL_ACCEPTANCE.md) | [Solução de problemas](TROUBLESHOOTING.md) |
| Revisar segurança | [Segurança](SECURITY.md) | [Arquitetura](ARCHITECTURE-AND-TESTS.md) |
| Atualizar hashes oficiais | [Releases e atualizações](RELEASE_AND_UPDATES.md) | [Build e reprodutibilidade](BUILD_REPRODUCIBILITY.md) |
| Sincronizar/atualizar 24 fontes upstream | [Códigos-fonte upstream](UPSTREAM_SOURCES.md) | [Releases e atualizações](RELEASE_AND_UPDATES.md) |
| Consultar API ou CLI | [Referência de API/CLI](API_REFERENCE.md) | [Arquitetura e testes](ARCHITECTURE-AND-TESTS.md) |
| Contribuir com código | [Desenvolvimento](DEVELOPMENT.md) | [Arquitetura e testes](ARCHITECTURE-AND-TESTS.md) |

## 📚 Catálogo completo

### 👤 Uso e operação
- [Instalação — requisitos, primeira execução e desligamento](INSTALLATION.md)
- [Configuração — variáveis de ambiente e limites](CONFIGURATION.md)
- [Guia do usuário — painel, biblioteca, sessões e storage](USER_GUIDE.md)
- [Matriz de emuladores — disponibilidade e limites por ID](EMULATOR_MATRIX.md)
- [Sistemas originais e menus reais](ORIGINAL_SYSTEM_UI.md)
- [Fontes de jogos e conteúdo autorizado](GAME_SOURCES.md)
- [Solução de problemas](TROUBLESHOOTING.md)
- [Referência de API e CLI — rotas, payloads e erros](API_REFERENCE.md)

### 🛡️ Segurança e evidências
- [Modelo de segurança](SECURITY.md)
- [Ambientes isolados](ISOLATED_ENVIRONMENTS.md)
- [Checklist de aceitação no host](LOCAL_ACCEPTANCE.md)
- [Arquitetura, testes e limites de validação](ARCHITECTURE-AND-TESTS.md)

### 🧰 Engenharia e manutenção
- [Build e reprodutibilidade](BUILD_REPRODUCIBILITY.md)
- [Referência de API e CLI](API_REFERENCE.md)
- [Política de release e atualização](RELEASE_AND_UPDATES.md)
- [Guia de desenvolvimento e contribuição](DEVELOPMENT.md)
- [Histórico de mudanças](../CHANGELOG.md)

## 🚦 Vocabulário de estado

| Termo | Significado |
|---|---|
| **Perfil** | Definição de ambiente, sistema e estratégia no catálogo. Não prova disponibilidade do executável. |
| **Asset pinado** | Arquivo oficial com versão/referência e hash fixados no `release-lock.json`. Não prova execução funcional. |
| **`skip-upstream`** | EmuStack não instala aquele asset a partir de uma fonte upstream fixada no lock atual; o motivo fica declarado. |
| **Launcher encontrado** | Um executável reconhecido está presente. Não prova que abra, que renderize ou que rode um jogo. |
| **Pré-requisitos detectados** | Arquivos/caminhos básicos foram encontrados. Não prova autenticidade, integridade funcional ou boot bem-sucedido. |
| **Aceitação de runtime** | Os probes automatizados da topologia/API/capacidades selecionadas passaram nesta execução/host. |
| **Boot comprovado** | Um teste manual registrou um sistema/jogo real iniciando no host, com os arquivos e versão informados. |
| **Não suportado** | A ação não deve ser simulada nem encaminhada para um runner inexistente/não verificado. |

## 🔗 Fonte de verdade

- `catalog.json`: catálogo de emuladores/launchers reconhecidos.
- `environments.json`: 20 IDs, estratégia e dados de cada ambiente.
- `console-systems.json`: perfis e estratégias para sistemas originais/menu.
- `game-sources.json`: fontes e orientação por perfil.
- `release-lock.json`: estado dos assets upstream fixados, incluindo motivos de `skip-upstream`.
- `install-report.json`: resultado produzido pelo build no host/runner.
- `data/runtime-acceptance.json`: relatório local de aceitação, que deve ser revisado antes de compartilhar.
- `CHANGELOG.md`: histórico de alterações visíveis.
