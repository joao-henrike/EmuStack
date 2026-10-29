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

## 🗃️ Repositórios APT

No padrão, o build utiliza repositórios Trixie atuais para receber atualizações; assim, as versões de pacotes podem mudar mesmo que a imagem base esteja pinada. Para selecionar um snapshot datado:

```bash
APT_SNAPSHOT_TIMESTAMP=20261027T000000Z FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh
```

O timestamp é ilustrativo: escolha uma data revisada. Snapshot melhora a estabilidade da resolução, mas também congela correções de segurança posteriores. Reavalie regularmente e não trate um snapshot antigo como política permanente de atualização. Veja [Debian Snapshot](https://snapshot.debian.org/).

## 🔐 Assets oficiais no release lock

O `release-lock.json` atualmente é estrito e cobre os 20 IDs. O estado verificado consiste em **11 assets baixáveis oficiais com SHA-256** e **9 entradas `skip-upstream`** com razão explícita. Os modos `pinned` e `pinned-url` fixam referência/URL e hash do asset baixado; `skip-upstream` significa que o asset não é instalado pelo caminho upstream pinado nessa entrada.

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

## ⚠️ Limites de reprodutibilidade

O digest da imagem base é pinado, mas APT continua temporal por padrão. Toolchain, arquitetura, Docker/BuildKit, flags, fonte upstream, build de dependências e backend gráfico influenciam o resultado. A política atual busca repetir assets conhecidos, não oferecer uma promessa de bit-for-bit reproducibility. Builds experimentais podem falhar e devem continuar assim identificados.
