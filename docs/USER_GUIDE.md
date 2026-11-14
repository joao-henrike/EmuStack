# 🎮 Guia do usuário

O painel organiza ambientes isolados e fornece uma forma controlada de consultar pré-requisitos e solicitar ações. Ele não substitui a interface do emulador nem prova que qualquer jogo seja compatível.

## 🧭 Seções do dashboard

| Seção | Para que serve | Atenção |
|---|---|---|
| **Visão geral** | Resumo do serviço, perfis e sessões. | Saúde do serviço não é sinônimo de emulador instalado. |
| **Ambientes isolados** | Estado de cada agente, binário detectado, pastas e limites declarados. | Confirme o relatório de instalação do build. |
| **Sistemas originais** | Pré-requisitos e rotas de BIOS/firmware/menu quando disponíveis. | Interface HTML não reproduz um sistema original. |
| **Emuladores** | Catálogo, launchers reconhecidos e informações do perfil. | Executável encontrado não garante jogo funcional. |
| **Biblioteca** | Arquivos encontrados por ambiente com o ID do perfil visível. | A biblioteca não copia nem converte arquivos entre sistemas. |
| **Fontes de jogos** | Índice por categoria e por console para conteúdo publicado/licenciado. | Fontes são pontos de descoberta, não garantia jurídica ou técnica. |
| **Sessões** | Consultar filtros, estado dos processos, logs e encerramento individual pela nova aba dedicada. | A janela gráfica pode depender do display e dos drivers do host. |
| **Relatório de instalação/aceitação** | Verificar ativos e probes disponíveis. | Relatórios podem expor informações do host; revise antes de compartilhar. |


## 📺 Fase 2 — modo TV, controle e tela cheia

Use o botão **Modo TV** na barra superior para ampliar fontes e alvos. O botão de ajustes (⚙) abre as preferências locais: ativar a navegação por controle, reforçar contraste e reduzir animações. A preferência de movimento reduzido do sistema também é respeitada. Configurações são guardadas apenas no armazenamento local do navegador e não são enviadas ao backend; se o armazenamento for bloqueado, valem apenas até o recarregamento.

No modo TV, as **setas** do teclado percorrem comandos visíveis e **Enter** ativa o comando focado. Campos de texto e seletores preservam o comportamento normal. Em um navegador com Gamepad API, D-pad e analógico movem o foco, **A/Cross** ativa, **B/Circle** fecha um diálogo ou volta para o início, **Start/Options** abre ajustes. A leitura do controle é feita somente com modo TV e suporte a controle ativados, enquanto a página está visível. Cada acionamento exige liberar o botão antes de repetir. A compatibilidade e o mapeamento variam conforme o navegador e o dispositivo.

A opção de **tela cheia** usa a API do navegador mediante ação explícita; não é restabelecida automaticamente e pode ser recusada. Nenhuma opção muda resolução, drivers, Vulkan, renderizador, áudio ou as preferências internas dos emuladores. Consulte a [aceitação local](LOCAL_ACCEPTANCE.md) para testes físicos.

A aba **Sessões** permite filtrar processos ativos/finalizados, consultar logs e pedir encerramento de cada sessão. O botão **Atualizar sessões** consulta a API existente; não faz polling contínuo. O filtro não altera processos nem remove saves. Para detalhes de implementação e limites, veja [Fase 2](PHASE2_IMPLEMENTATION.md).

## 📂 Adicionar jogos próprios

Copie o arquivo para a pasta correspondente ao perfil, por exemplo:

```text
data/environments/rpcs3/games/
data/environments/pcsx2/games/
data/environments/dolphin/games/
```

Use sempre o diretório do ID correto. A raiz `games/` é montada read-only para o agente; a leitura é suficiente para iniciar arquivos suportados, enquanto o emulador deve salvar configurações/saves nas áreas graváveis dele.

O scanner não é um verificador de compatibilidade. Extensão, nome do arquivo, região ou hash não garantem que o título rode. O agente rejeita paths absolutos, travessia `..`, symlinks e itens que não sejam arquivos regulares. Arquivos ocultos, extensões não reconhecidas e resultados além do limite da biblioteca podem não aparecer.

Não utilize uma pasta global antiga esperando que os agentes compartilhem seu conteúdo. Essa forma de compartilhamento foi removida para preservar a separação.

## 🧩 BIOS, firmware, NAND, MLC e discos de sistema

Arquivos autorizados necessários ao boot devem ficar na raiz privada do perfil correto:

```text
data/environments/<id>/bios/    # arquivos de boot/BIOS montados read-only
data/environments/<id>/home/    # configs e estado persistente do emulador
data/environments/<id>/saves/   # área de saves, quando usada pelo emulador
```

Alguns emuladores instalam firmware em `home/`, enquanto outros leem dumps de `bios/`; NAND, MLC e HDD dependem do emulador. Siga o procedimento oficial para a versão utilizada e evite renomear arquivos aleatoriamente para satisfazer um teste de caminho.

EmuStack não fornece nem baixa ROMs, BIOS, firmware, chaves, NAND, MLC ou HDDs proprietários. Ver um arquivo no scanner apenas prova que ele foi encontrado sob certos critérios — não que você tem direito de usá-lo, nem que ele é autêntico ou válido.

## 🗃️ Saves, configurações e logs

- `saves/` é uma área persistente separada, mas não existe um caminho universal: alguns emuladores gravam saves/configurações dentro de `home/`.
- Logs do EmuStack ficam em `data/environments/<id>/home/.local/state/emustack/logs/`.
- Os cinco diretórios `games`, `bios`, `saves`, `home` e `emulators` são próprios de cada ID.
- Não edite ou restaure uma raiz enquanto o emulador está ativo: o snapshot pode ficar inconsistente.

## 💾 Armazenamento, backup e restauração

Inspecione primeiro:

```bash
python3 scripts/manage-storage.py init
python3 scripts/manage-storage.py inspect
python3 scripts/manage-storage.py inspect rpcs3
```

Crie um backup e restaure apenas após confirmar o perfil/arquivo:

```bash
python3 scripts/manage-storage.py backup rpcs3
python3 scripts/manage-storage.py restore rpcs3 backups/rpcs3/ARQUIVO.tar.gz
```

O backup inclui um manifesto e SHA-256 por arquivo. A restauração valida conteúdo, paths, links e associação ao perfil, usa staging e guarda rollback antes de substituir a raiz. O script verifica o estado do serviço via Docker; pare o agente antes do backup. O arquivo `ARQUIVO.tar.gz` é um placeholder: substitua pelo nome real gerado.

Para criar um disco de dados **vazio** (não é firmware nem imagem bootável):

```bash
python3 scripts/manage-storage.py create-disk xemu --size 8G --format qcow2
```

Isso requer `qemu-img`/pacote `qemu-utils` no host. A imagem não contém partições ou dashboard do Xbox.

## 🖥️ Inicializar um sistema/menu original

Abra a seção **Sistemas originais**, escolha o perfil e leia o estado, os checks e as instruções antes de solicitar o boot. As rotas dependem de binário detectado, estratégia upstream, display, firmware e outros arquivos válidos. Os perfis marcados como não suportados permanecem bloqueados.

Para Xbox original, a confirmação do dashboard é uma declaração manual vinculada ao SHA-256 do HDD configurado. Ela impede reutilizar acidentalmente uma confirmação para outro arquivo, mas não inspeciona nem autentica automaticamente o conteúdo. Confira [Sistemas originais](ORIGINAL_SYSTEM_UI.md).

## 🧾 Fontes e legalidade de conteúdo

A seção de fontes lê `game-sources.json`; veja o guia [Fontes de jogos e conteúdo autorizado](GAME_SOURCES.md). Cada item exige verificação própria de licença, termos, formato e compatibilidade. O projeto não inclui download automático de jogos comerciais.

## 🛠️ Diagnóstico rápido

```bash
docker compose ps
docker compose logs --tail=200 dashboard
docker compose logs --tail=200 env-rpcs3
curl -i http://127.0.0.1:8765/api/health
```

O endpoint de saúde é apenas um sinal básico de vida; ele não expõe um relatório de auditoria completo. Para API de controle, use o dashboard local e não encaminhe a porta para a rede. Consulte [Solução de problemas](TROUBLESHOOTING.md).

## 🛠️ Instalar ou reverter um executável por perfil

Para administrar os executáveis extras de uma pasta privada, abra um terminal no host e consulte `python3 scripts/emulator-manager.py status`. Essa ação não fica exposta ao dashboard para preservar as fronteiras de segurança. O host pode compilar cinco projetos com receitas opt-in, importar um binário revisado por SHA-256, e reverter/remover uma instalação gerenciada. Veja [Guia de instalações e rollback](EMULATOR_MANAGER.md); pare a sessão antes de substituir um executável.

## 🧯 Encerrar uma sessão com segurança

Use o painel para finalizar uma sessão iniciada ali e confira o estado antes de encerrar o contêiner. Para parar a stack, use o comando Compose correspondente à configuração com a qual ela foi iniciada; não remova volumes ou pastas de dados como primeira medida de diagnóstico.
