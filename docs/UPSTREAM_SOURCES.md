# 📦 Códigos-fonte upstream dentro do EmuStack

O EmuStack registra **20 perfis**, dos quais **18 têm projetos de emulador identificados** e **2 (Xbox One e Xbox Series) continuam sem runner suportado**. Os 18 projetos são representados por **24 repositórios Git oficiais**: Mupen64Plus necessita do núcleo, interface e cinco plugins oficiais, todos com commits independentes. A política de inclusão de fontes não altera os limites de compatibilidade dos consoles.

## O que foi migrado

A pasta `third_party/` usa **submódulos Git** com URLs HTTPS oficiais e commits imutáveis no índice Git do EmuStack. Ao sincronizar, os arquivos completos de cada projeto aparecem dentro de `third_party/<id>/`. O código e o histórico completos **não são copiados para os objetos Git do repositório EmuStack**; a clone/sincronização exige acesso às origens oficiais. Isso não é uma migração física por `git subtree` nem um mirror independente. Não confundir o conteúdo presente no checkout com código incorporado ao repositório principal.

Metadados em `upstream/source-lock.json`, origens em `.gitmodules`, e versão fixada do submódulo no índice Git devem concordar. Nenhum `git pull` em um submódulo atualiza automaticamente o release usado: updates exigem pin explícito e revisão.

## Migração sincronizada de todos os emuladores

A partir da raiz do projeto, após salvar alterações locais e atualizar a branch:

```bash
python3 scripts/upstream-manager.py audit
python3 scripts/upstream-manager.py sync --jobs 4
python3 scripts/upstream-manager.py audit --require-checkout
```

Clone novo: `git clone --recurse-submodules --branch fix/dashboard-degraded-startup https://github.com/joao-henrike/EmuStack.git`. Se o clone já existe, use `git pull --ff-only` e depois `sync`. O sincronizador inicializa os 24 repositórios em lote, podendo consumir múltiplos gigabytes de disco e tráfego. Ele não executa fontes nem compila os emuladores. Dependências internas de submódulos de terceiros precisam de auditoria antes de usar `--recursive`.

## Como atualizar um módulo sem alterar os outros

```bash
python3 scripts/upstream-manager.py plan --id ppsspp
# Inspecione mudanças, licença, compatibilidade e hash antes de escolher o commit.
git switch -c chore/update-ppsspp-source
python3 scripts/upstream-manager.py pin ppsspp <SHA_COMPLETO_DE_40_CARACTERES>
python3 scripts/upstream-manager.py audit --require-checkout
bash scripts/validate-project.sh
git diff --cached --submodule=log
git commit -m "chore(upstream): pin reviewed PPSSPP source commit"
```

`plan` sem `--id` consulta o HEAD oficial de todos os 24 componentes. O comando apenas informa diferenças; não baixa nem atualiza por conta própria. O comando `pin` só opera em branch não principal, exige checkout limpo, busca o hash especificado na origem e **prepara** o diff para uma revisão/PR. Não há atualização automática silenciosa.

## Integração com builds de host (Fase 1)

Além do sincronizador de fontes, o `scripts/emulator-manager.py` permite construir **KytyPS5, shadPS4, PPSSPP, melonDS e bsnes** a partir dos commits fixados, após revisar dependências e consentir explicitamente em executar código upstream. Saída privada em `data/environments/<id>/emulators/`, com backup e rollback controlados. **Não substitui** a instalação oficial em Docker por release lock, não compila automaticamente os outros 13 projetos e não prova que os quatro builds funcionem no host. Consulte [Gerenciador de emuladores](EMULATOR_MANAGER.md).

## Limites e licenças

- As licenças e avisos de copyright pertencem a **cada upstream**. O MIT do EmuStack não se sobrepõe às licenças de `third_party`. Inspecione os avisos e requisitos dos 24 repositórios antes de redistribuir versões ou builds.
- `upstream/source-lock.json` fixa **código-fonte**, enquanto `release-lock.json` fixa **assets binários**. Um não substitui o outro. Os Dockerfiles e o instalador existentes ainda utilizam fontes de binários oficiais/APT e não recompilam automaticamente cada checkout.
- Sem ROMs, BIOS, firmware, chaves de console, jogos comerciais ou assets protegidos distribuídos.
- A sincronização é explícita; não requer token em código nem permite fontes de hosts desconhecidos.
- GitHub Actions pode falhar antes da alocação de um runner. Só se considera CI verificado após haver logs/etapas executadas com sucesso.

Fontes oficiais: as URLs individuais e commits completos estão no `upstream/source-lock.json`. O Eden é obtido pelo Forgejo próprio `git.eden-emu.dev`, não por um mirror de procedência desconhecida.
