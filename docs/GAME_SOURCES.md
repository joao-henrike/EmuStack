# Fontes de jogos e conteúdo autorizado

> **EMUSTACK // GAMING LAB** · [README](../README.md) · [Instalação](INSTALLATION.md) · [Guia do usuário](USER_GUIDE.md) · [Matriz de emuladores](EMULATOR_MATRIX.md) · [Segurança](SECURITY.md) · [Identidade visual](IDENTIDADE-VISUAL.md)

EmuStack é um organizador e lançador; não é um site de ROMs. O projeto não baixa, inclui ou distribui jogos comerciais, ROMs, discos, BIOS, chaves ou firmware. A aba **Fontes de jogos** reúne lojas oficiais, índices de homebrew/demos e documentação. Ela permite filtrar as recomendações por console; isso não significa que um emulador ou repositório baixe jogos automaticamente.

## Lojas oficiais

- [Steam](https://store.steampowered.com/) — jogos de PC; confirme compatibilidade com Linux na página de cada produto.
- [GOG](https://www.gog.com/) — catálogo de jogos para PC; confira os requisitos e os termos de cada item.
- [itch.io](https://itch.io/) — jogos independentes, demos e freeware publicados pelos criadores.
- [Xbox para PC](https://www.xbox.com/pt-BR/xbox-on-pc) — títulos com versão para Windows e ofertas de jogos Xbox disponíveis no PC.
- [PlayStation Store Brasil](https://store.playstation.com/pt-br/) — loja oficial PlayStation.
- [Nintendo Store](https://www.nintendo.com/pt-br/store/games/) — loja oficial Nintendo.

**Importante:** comprar uma versão de PC ou console numa loja não significa que você recebeu um arquivo de jogo que possa ser usado diretamente por um emulador. Confira o formato, os termos da plataforma e a documentação do emulador.

## Homebrew, demos e freeware

- [PDRoms](https://pdroms.de/) — coleção comunitária que declara ter predominantemente freeware, donationware, open-source, public-domain ou itens autorizados. A licença de cada item ainda deve ser conferida.
- [PPSSPP — guia oficial de demos e homebrew](https://www.ppsspp.org/docs/getting-started/how-to-get-demos-and-homebrew/) — orientação específica para demos PSP e homebrew.
- [itch.io — homebrew gratuito](https://itch.io/games/free/tag-homebrew) — filtro de descoberta, não garantia de licença ou formato de ROM.
- [itch.io — homebrew NES ROM](https://itch.io/games/free/tag-homebrew/tag-nes-rom) — filtro de projetos NES, publicados por seus autores.

- [GameBrew](https://www.gamebrew.org/wiki/Main_Page) — wiki comunitária para descobrir projetos, ferramentas e conteúdo homebrew.
- [itch.io: tag homebrew](https://itch.io/games/tag-homebrew) — projetos publicados por criadores independentes.
- [GitHub: homebrew-game](https://github.com/topics/homebrew-game) — repositórios comunitários; confira a release e a licença de cada projeto.

A classificação como “homebrew” ou “gratuito” não garante automaticamente redistribuição autorizada. Confirme que o autor publicou o arquivo e que a licença permite baixar, executar e redistribuir quando aplicável. Prefira a página oficial do projeto.

## Sua própria biblioteca

Se a lei local, os termos da plataforma e as circunstâncias permitirem, organize arquivos que você possua ou criou e esteja autorizado a usar. Não há uma regra universal que permita fazer cópias de todo jogo, remover proteções ou usar qualquer firmware. EmuStack não fornece instruções de bypass nem distribui arquivos de sistema.

## Formatos não são compatibilidade

A biblioteca reconhece extensões comuns (`.iso`, `.chd`, `.cue`, `.pkg`, `.elf`, `.rvz`, `.wbfs`, `.nsp`, `.xci`, `.3ds`, `.cia`, `.nds`, `.gba`, `.nes`, entre outras). Isso ajuda a organizar; não é uma certificação do conteúdo nem uma garantia de que um emulador aceite aquele formato.


## Como a lista por console funciona

O catálogo `game-sources.json` contém `platform_guidance` para os 20 perfis EmuStack. A interface filtra fontes de descoberta adequadas e mostra uma nota específica sobre cada ambiente. Os IDs representam perfis de emulação, não uma afirmação de que o sistema completo ou o dashboard original é suportado.

A regra é deliberadamente conservadora:

- Repositórios oficiais de emuladores são fontes para o programa do emulador, não para jogos comerciais.
- Lojas oficiais são fontes para versões oferecidas naquela loja; uma versão de PC ou compra digital não se transforma automaticamente em arquivo de console utilizável no emulador.
- Homebrew e demos podem ser utilizados somente quando o autor os publica em formato compatível e com autorização apropriada. Um filtro ou site comunitário não garante os direitos de cada item.
- Para jogos comerciais, não há links de downloads não autorizados. Use apenas arquivos que você tenha autorização para copiar e utilizar, observando a legislação local e os termos da plataforma.

O EmuStack não tem mecanismo de download de jogos, scraping, torrent ou instalação automática de conteúdo de terceiros. O usuário decide o que importar para `data/environments/<id>/games/` e é responsável por verificar origem, licença, integridade e compatibilidade.
