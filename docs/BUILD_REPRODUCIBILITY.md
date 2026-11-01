# 📦 Build, lock de assets e reprodutibilidade

## 🎯 Escopo do que é fixado

A reprodutibilidade é parcial e explícita. Há três fontes que precisam ser consideradas separadamente:

1. digest da imagem base Debian;
2. versões dos pacotes APT;
3. assets de emuladores baixados/compilados.

O commit do `release-lock.json` deve ser consultado junto com o relatório de instalação do build. **Um hash de asset não é certificado de compatibilidade, segurança ou execução do emulador.**

## 🐧 Imagem base Debian

O Dockerfile fixa o digest multi-plataforma observado para a imagem oficial `debian:trixie-slim`:

```text
sha256:89c1ea91e897f0fe0a3731595330bc45b8bdef4047464a07116f891a94054b31
```

A revisão futura deve conferir o digest oficial, origem e estado de segurança antes de atualizá-lo. Referência: [tags oficiais da imagem Debian](https://hub.docker.com/_/debian/tags/).

## 🌐 Proxy local do dashboard

O serviço `dashboard-proxy` usa a imagem oficial `nginx:alpine` fixada pelo digest multi-plataforma `sha256:785835ea65db4bba6f021acc0f3be91b0fef76a53fe41f8588c6698d2aed0606`. O digest foi conferido no manifesto oficial em 21 de outubro de 2026. Consulte o [manifesto de tags e digests do Nginx oficial](https://github.com/docker-library/repo-info/blob/master/repos/nginx/remote/alpine.md) antes de qualquer atualização. O proxy não faz parte do release lock dos emuladores.
## 🗃️ Repositórios APT

No padrão, o build utiliza repositórios Trixie atuais para receber atualizações; assim, as versões de pacotes podem mudar mesmo que a imagem base esteja pinada. Para selecionar um snapshot datado:

A imagem inclui `/usr/games` no `PATH`: no Debian Trixie, os executáveis dos pacotes `dolphin-emu` e `mupen64plus-ui-console` ficam nesse diretório. Esses fallbacks são pacotes Debian, não assets upstream do `release-lock.json`; a versão depende dos repositórios/snapshot APT usados no build.

```bash
APT_SNAPSHOT_TIMESTAMP=20261027T000000Z FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh
```

O timestamp é ilustrativo: escolha uma data revisada. Snapshot melhora a estabilidade da resolução, mas também congela correções de segurança posteriores. Reavalie regularmente e não trate um snapshot antigo como política permanente de atualização. Veja [Debian Snapshot](https://snapshot.debian.org/).

## 🔐 Assets oficiais no release lock

O `release-lock.json` atualmente é estrito e cobre os 20 IDs. O estado verificado consiste em **11 assets baixáveis oficiais com SHA-256** e **9 entradas `skip-upstream`** com razão explícita. Os modos `pinned` e `pinned-url` fixam referência/URL e hash do asset baixado; `skip-upstream` significa que o asset não é instalado pelo caminho upstream pinado nessa entrada.

No lock atual, Vita3K usa o release versionado `Vita3K/Vita3K-builds@4246` e o asset `Vita3K-x86_64.AppImage`; DuckStation usa o asset `DuckStation-x64-SSE2.AppImage` do canal `preview`, com o SHA-256 atual fixado. Como `preview` é um canal móvel, a próxima substituição upstream deve falhar no hash até que o lock seja revisado deliberadamente.

O lock não afirma que:
- todo perfil tem binário instalado/compatível com Linux;
- o binário abre ou executa jogos;
- os firmwares/BIOS do usuário são válidos;
- o sistema original inicializa;
- a compilação é bit a bit idêntica em arquiteturas e builders diferentes.

O lock atual **não cobre uma compilação fonte do KytyPS5**. A geração do lock foi feita com o build opcional desativado (`BUILD_KYTYPS5=0`); qualquer validação daquele caminho deve ser registrada separadamente.

## 🔄 Atualizar o lock manualmente via workflow

O workflow **Freeze official emulator release assets** é acionado manualmente por `workflow_dispatch`:
1. inicia em workspace temporário com lock não estrito para descobrir assets disponíveis;
2. constrói usando os downloads oficiais permitidos;
3. exporta candidato com hashes dos assets realmente instalados;
4. valida cobertura e integridade;
5. tenta reconstruir em modo de lock estrito;
6. publica o candidato como artifact do workflow, para revisão.

Não substitua `release-lock.json` sem conferir artifact, diff, hashes, fontes upstream, licenças e logs de build. Preserve entradas `skip-upstream` com razões honestas; não pinne binários não validados para fazer a tabela parecer completa. Passo a passo: [Releases e atualizações](RELEASE_AND_UPDATES.md).

## 🧪 Sequência de validação sugerida

```bash
./scripts/validate-project.sh
docker compose -f compose.yaml config --quiet
./scripts/build-and-audit.sh
./scripts/runtime-acceptance.sh
```

Para exportar lock candidato no próprio build quando isso for intencional:

```bash
FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh
```

Antes de aceitar a mudança, valide o rebuild estrito, veja o relatório do asset e teste o runtime. Nunca use somente o nome de tag ou a resposta HTTP do upstream como verificação de integridade.

## 🧰 Builds locais de fonte pinada — gerenciador de host

O gerenciador `scripts/emulator-manager.py` possui receitas explícitas para KytyPS5, shadPS4, PPSSPP, melonDS e bsnes. Para essas cinco integrações, ele confere commit do submódulo, gitlink no índice, ausência de modificações e submódulos internos consistentes antes do build. Compila em cópia temporária, registra log e SHA-256 do executável e mantém rollback do binário anterior por perfil.

Isso **não** torna o build bit a bit reproduzível: toolchain, bibliotecas, flags, sistema e dependências aninhadas ainda variam conforme o host. Os outros 13 projetos pinados não têm receita genérica de compilação nesta etapa, embora 11 assets binários do Docker estejam fixados pelo release lock e fallbacks Debian sejam utilizados. Consulte [Gerenciador de emuladores](EMULATOR_MANAGER.md).

## Git temporário para builds de fonte

O gerenciador recria metadados Git para cada repo na cópia temporária, incluindo submódulos FFmpeg. Os objetos originais são acessados por alternates sem alterações dos repositórios pinados, garantindo que o SHA consultado no estágio seja do projeto upstream, não do EmuStack. Isso não torna um build bit a bit reproduzível, nem certifica dependências de runtime.

## ⚠️ Limites de reprodutibilidade

O digest da imagem base é pinado, mas APT continua temporal por padrão. Toolchain, arquitetura, Docker/BuildKit, flags, fonte upstream, build de dependências e backend gráfico influenciam o resultado. A política atual busca repetir assets conhecidos, não oferecer uma promessa de bit-for-bit reproducibility. Builds experimentais podem falhar e devem continuar assim identificados.
