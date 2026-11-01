# Fase 1 — Implementação Docker-first e critérios de aceitação

**Escopo:** branch `fix/dashboard-degraded-startup`; não foi mesclada à `main`. Este documento descreve o código preparado para a Fase 1, **não equivale a atestado de compilação, execução gráfica, suporte a ROM ou boot de console**.

## Arquitetura de operação

- Uma única interface `bash scripts/phase1.sh` no host chama contêineres não-root: toolchain CMake/Ninja/Clang, Qt6, SDL2/SDL3 e Python/Node ficam na imagem Debian Trixie.
- `validate`, `test`, `status`, `deps`, `plan-deps`, `history` e `logs` não têm rede; `build`, `build-all` e `sync-deps` precisam de rede. Somente `sync-deps`, com confirmação explícita, reabre o checkout `third_party/` e o banco `.git/` para gravar commits de dependências **pinados**.
- O build não tem Docker socket, privilegios elevados ou acesso de escrita a jogos, BIOS e saves. Sua área de saída é o estado do gerenciador mais `data/environments/<perfil>/emulators/`; mantém CPU/RAM/processos limitados.
- A imagem de execução é separada da de build: os agentes recebem somente seu volume `emulators:ro` e bibliotecas de runtime declaradas na imagem, sem toolchain.

## Perfis

| Perfil | Fonte fixada | Receita de build | Payload de runtime esperado |
|---|---|---|---|
| KytyPS5 | Sim | CMake/Ninja + Clang | `kyty_launcher`, `kyty_emulator`, updater, plugins Qt, `qt.conf` e bibliotecas entregues pelo instalador upstream |
| shadPS4 | Sim | CMake/Ninja | `shadPS4` e bibliotecas resolvidas na imagem runtime |
| PPSSPP | Sim | CMake/Ninja + SDL3/SDL3_ttf | `PPSSPPSDL` e diretório `assets` da fonte pinada |
| melonDS | Sim | CMake/Ninja + Qt6/SDL2 | `melonDS` e bibliotecas resolvidas na imagem runtime |
| bsnes | Sim | Make com `local=false` | `bsnes`, banco de jogos e shaders da fonte pinada |

Outros 13 perfis permanecem sob gestão de releases oficiais fixados, instalador APT e importação explícita de binários com SHA-256; **não** foi acrescentada receita de build genérica para todos os 18 projetos. Xbox One e Xbox Series permanecem sem runner compatível confirmado, por isso a instalação segue bloqueada.

## Gerenciamento de versões e atualização

1. Antes do download de fontes, `plan-deps` mostra origens/gitlinks; `sync-deps` exige opção explícita e confere commits e hosts de confiança.
2. `build` compila em cópia temporária preservando o SHA Git dos submódulos e prepara um pacote por console, sem executar o jogo.
3. `install_build_bundle` copia o payload inteiro para `.emustack-bundles/<sha256-prefix>` **dentro da pasta exclusiva do perfil**; arquivos são conferidos por hash e links simbólicos são rejeitados.
4. Um launcher POSIX na raiz do mount aponta para o pacote exato. Atualizar esse launcher preserva a versão anterior e seus metadados; `rollback` restaura o pacote original, recusando conteúdo alterado.
5. `uninstall` remove somente o launcher gerenciado. Os diretórios de versões anteriores são preservados por segurança e para rollback: limpeza agressiva **não é automática**. `purge <id> --yes-delete-managed-backups` pode apagar backups/bundles órfãos apenas depois da desinstalação, sem tocar em jogos/saves/BIOS. Isso elimina a possibilidade de rollback.
6. `install-file` só importa arquivo local já revisado em `data/imports/`, com nome no catálogo e SHA-256 explícito; não busca binários de sites arbitrários.

Os hashes demonstram integridade perante o conteúdo armazenado, **não autenticidade das fontes nem compatibilidade funcional**. O fluxo não atualiza silenciosamente `release-lock.json` ou `source-lock.json` e não distribui ROMs, BIOS ou firmware de console.

## Contrato de CLI

```bash
bash scripts/phase1.sh status
bash scripts/phase1.sh deps melonds
bash scripts/phase1.sh plan-deps ppsspp
bash scripts/phase1.sh sync-deps ppsspp --yes-download-submodules --jobs 2
bash scripts/phase1.sh build melonds --yes-run-upstream-code --jobs 2
bash scripts/phase1.sh build-all --yes-run-upstream-code --jobs 2
bash scripts/phase1.sh history melonds
bash scripts/phase1.sh rollback melonds
bash scripts/phase1.sh uninstall melonds
bash scripts/phase1.sh purge melonds --yes-delete-managed-backups
bash scripts/phase1.sh logs melonds
bash scripts/phase1.sh test
bash scripts/phase1.sh validate
```

Para importação de executável já adquirido legalmente e cujo hash foi verificado:

```bash
mkdir -p data/imports
# Colocar o arquivo revisado dentro de data/imports antes de prosseguir
bash scripts/phase1.sh install-file ppsspp PPSSPPSDL HASH_SHA256_REAL PPSSPPSDL
```

Os comandos de compilação executam código de projetos upstream: só devem ser usados depois de inspecionar fontes, licenças, requisitos de memória e eventuais downloads auxiliares.

## Aceitação planejada para a etapa posterior

**A implementação de código não fecha os testes.** Quando for iniciada a aceitação:

- Executar `bash scripts/phase1.sh validate` e verificar testes de regressão, Shell, JavaScript e locks.
- Executar os cinco builds num ambiente Docker com versões reais das dependências e registrar arquivos, SHA-256, commits e logs.
- Executar `bash scripts/phase1-acceptance.sh` após reconstruir a imagem runtime: verifica, nos agentes correspondentes, o pacote, seus recursos e bibliotecas `ldd` ausentes, sem abrir jogo.
- Abrir individualmente as cinco interfaces com integração gráfica/áudio/controle; capturar erros, crash e problemas de plugins, verificar encerramento e saves com conteúdo homebrew/autorizado.
- Exercitar instalação, atualização, rollback após upgrade/desinstalação e detectar adulteração de assets, sem tocar nos saves.
- Só então declarar uma compilação ou execução aprovada. **Nenhuma dessas evidências de host/runtime está presumida por este documento.**

## Observações conhecidas

- O histórico local contém uma compilação/instalação do bsnes antes do novo empacotamento por diretório; ela não é evidência da receita Docker-first atual.
- Qt6 6.4.2, CMake 3.25 e SDL3 ausente bloquearam builds diretamente no host Bookworm. A solução de engenharia é **toolchain Trixie em Docker**, não instalar dependências Debian 13 no host.
- A imagem fixa o digest Debian base, mas ainda usa APT sem snapshot obrigatório: **bit-for-bit reproducibility não é garantida**.
- Os binários podem exigir bibliotecas e plugins do runtime que ainda precisam ser verificados. O status `managed_hash_valid` não representa execução aprovada.
- O projeto não pode garantir suporte a todas as plataformas do catálogo apenas por elas terem serviços e pastas isolados.
