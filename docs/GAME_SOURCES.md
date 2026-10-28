# Fontes de jogos por plataforma — EmuStack 0.7.1

## Uma distinção importante

Repositórios como RPCS3, PCSX2, Dolphin, PPSSPP, Xenia e outros publicam o **emulador** (código, binários e atualizações), não uma biblioteca de jogos comerciais para importar automaticamente. O EmuStack não raspa páginas, baixa, instala nem distribui ROMs, ISOs, imagens de discos, BIOS ou firmware.

A interface de Fontes de jogos filtra sugestões por categoria e por cada perfil. Os links abaixo são fontes de descoberta de homebrew/demos, lojas oficiais para as versões oferecidas nesses canais ou documentação. Eles não constituem uma autorização global: confira os direitos, a licença, a plataforma e o formato de cada item.

## Fontes de descoberta

| Fonte | Para que serve | Observações |
|---|---|---|
| [PDRoms](https://pdroms.de/) | Homebrew e software freeware para diferentes consoles e portáteis | O site informa que seu conteúdo é predominantemente freeware, donationware, open-source, public-domain ou autorizado. Verifique cada item. |
| [itch.io — homebrew](https://itch.io/games/tag-homebrew) | Jogos independentes e projetos homebrew publicados por seus autores | Pode incluir itens pagos, demos, jogos para browser ou arquivos para console. Veja a página individual. |
| [itch.io — homebrew gratuito](https://itch.io/games/free/tag-homebrew) | Descoberta de projetos homebrew com filtro de preço grátis | “Grátis” não significa automaticamente redistribuível nem compatível com emulador. |
| [itch.io — homebrew NES ROM](https://itch.io/games/free/tag-homebrew/tag-nes-rom) | Projetos NES que podem disponibilizar arquivo de ROM | Confirme formato, autorização e licença de cada projeto. |
| [GameBrew](https://www.gamebrew.org/wiki/Main_Page) | Índice comunitário de homebrew, ferramentas e projetos, especialmente Nintendo/portáteis | É um índice de descoberta. Siga a página do autor e confira a licença. |
| [GitHub — homebrew-game](https://github.com/topics/homebrew-game) | Descoberta de projetos abertos/homebrew e releases dos autores | A presença no GitHub não prova que o conteúdo seja livre de direitos. Confira a licença e a release oficial. |
| [PPSSPP — demos e homebrew](https://www.ppsspp.org/docs/getting-started/how-to-get-demos-and-homebrew/) | Guia oficial sobre demos PSP e homebrew | É a melhor referência específica para encontrar conteúdo PSP autorizado; não é um pacote de jogos comerciais. |

## Mapeamento por perfil

| Perfil / console | Fontes recomendadas no catálogo | Limite importante |
|---|---|---|
| PS5 (kytyps5) | itch.io, GitHub homebrew, mídia autorizada própria | Emulação experimental; não há boot completo de PS5 nem catálogo geral de jogos comerciais para emulador. |
| PS4 (shadps4) | itch.io, GitHub homebrew, mídia autorizada própria | Emulação experimental; compra na PS Store não vira automaticamente um arquivo para emulador. |
| PS3 (rpcs3) | PDRoms (se o item for realmente para PS3), itch.io/GitHub do autor | Use apenas homebrew ou arquivo que tenha autorização para uso. Firmware é separado. |
| PS1 (duckstation) | PDRoms, itch.io, GitHub homebrew | Confira que o item contém arquivo compatível de PS1. BIOS não incluso. |
| PS2 (pcsx2) | Releases de homebrew/autores no GitHub/itch.io; mídia autorizada própria | Não foi verificado um catálogo geral de ISOs comerciais PS2 com distribuição autorizada. BIOS não incluso. |
| PSP (ppsspp) | Guia oficial PPSSPP, PDRoms, itch.io e GitHub homebrew | Demos/homebrew podem funcionar; firmware para VSH é separado e experimental. |
| PS Vita (vita3k) | GitHub/itch.io dos próprios autores; mídia autorizada própria | Não há catálogo amplo verificado de jogos Vita comerciais autorizados nesta lista. A UI do Vita3K não é o LiveArea original. |
| Xbox One (xbox-one) | Nenhuma fonte de arquivo para emulador recomendada | O runner está bloqueado/indisponível neste projeto. |
| Xbox 360 (xenia-canary) | GitHub homebrew dos autores; mídia autorizada própria | Focado em jogos; não oferece boot completo do dashboard retail neste projeto. |
| Xbox Series (xbox-series) | Nenhuma fonte de arquivo para emulador recomendada | Não há runner completo integrado; perfil bloqueado. |
| Xbox original (xemu) | PDRoms/itch.io/GitHub se o autor publicar especificamente para Xbox original; mídia autorizada própria | BIOS/MCPX/HDD do sistema são arquivos separados e não estão incluídos. |
| Switch (eden) | GameBrew, itch.io ou GitHub dos autores | Priorize homebrew publicado para Switch; demos oficiais Nintendo não são ROMs para importar. |
| Wii U (cemu) | GameBrew, PDRoms quando aplicável, GitHub homebrew | Jogos e arquivos de sistema não são baixados automaticamente. |
| Wii/GameCube (dolphin) | GameBrew, PDRoms, itch.io/GitHub dos autores | Verifique o alvo real e o formato; NAND/BIOS pode ser separado. |
| 3DS/2DS (azahar) | GameBrew e GitHub homebrew | Confirme a página oficial do autor, os direitos e a compatibilidade. |
| Nintendo DS (melonds) | GameBrew, PDRoms, itch.io/GitHub dos autores | Demos/homebrew devem ser distribuídos com autorização. |
| GB/GBC/GBA (mgba) | PDRoms, itch.io, GitHub homebrew | Procure conteúdo criado para a plataforma correta e confirme o formato. |
| Nintendo 64 (mupen64plus) | PDRoms, itch.io, GitHub homebrew | Uma tag de gênero/plataforma não garante que o arquivo seja ROM para N64. |
| SNES (bsnes) | PDRoms, itch.io, GitHub homebrew | Confirme que a página do autor fornece um arquivo SNES e permite seu uso. |
| NES/clássicos (mesen) | itch.io NES homebrew ROM, itch.io homebrew grátis, PDRoms | Confira a licença e o formato de cada release. |

## Lojas oficiais não são repositórios de ROMs

- [Steam](https://store.steampowered.com/) e [GOG](https://www.gog.com/): versões para PC. Verifique Linux e os requisitos de cada jogo.
- [Xbox para PC](https://www.xbox.com/pt-BR/xbox-on-pc): jogos oferecidos para PC.
- [PlayStation Store Brasil](https://store.playstation.com/pt-br/): loja oficial PlayStation.
- [Nintendo Store Brasil](https://www.nintendo.com/pt-br/store/games/) e [demos gratuitas Nintendo](https://www.nintendo.com/pt-br/store/games/games-with-free-demos/): conteúdo para canais/dispositivos oficialmente suportados.

Comprar ou descarregar um jogo por uma loja não significa que a loja fornece um dump ROM/ISO compatível com o EmuStack. A versão PC não substitui automaticamente a versão de console.

## Mídia própria e direitos

O [guia informativo da Provenance sobre dumping de mídia física própria](https://github.com/Provenance-Emu/wiki/blob/master/installation-and-usage/roms/ripping-roms.md) descreve conceitos de cópias digitais pessoais, mas não é uma fonte de jogos. A legalidade de backups, cópia de mídia e medidas anticircunvenção depende da legislação local e dos termos aplicáveis; não assuma que possuir um disco autoriza qualquer método de cópia.

O EmuStack **não** baixa jogos automaticamente. O catálogo não inclui sites de distribuição não autorizada de jogos comerciais. Os ficheiros, se legitimamente utilizáveis, são colocados manualmente pelo utilizador na biblioteca do ambiente apropriado, por exemplo data/environments/duckstation/games/.
