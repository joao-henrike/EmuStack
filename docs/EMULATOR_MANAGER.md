# 🛠️ Fase 1 — Gerenciador de emuladores por perfil

O EmuStack possui **duas vias complementares de instalação**, que não devem ser confundidas:

1. **Imagem Docker oficial:** `release-lock.json`, pacotes Debian e `scripts/install-upstream.py` mantêm os executáveis oficiais já instalados durante o build. Reconstruir a imagem continua sendo a forma de renovar esses assets.
2. **Gerenciador de host:** `scripts/emulator-manager.py` mantém binários adicionais *somente* em `data/environments/<id>/emulators/`, que é montado **somente leitura** no agente daquele console. Não monta o socket Docker no dashboard, não executa comandos arbitrários pela API e não mexe nos arquivos de jogos/saves.

## Estado de integração (não confundir com compatibilidade)

| Perfil | Situação de Fase 1 |
|---|---|
| KytyPS5, shadPS4, PPSSPP, melonDS, bsnes | Receita de compilação Linux pinada, a partir do checkout de `third_party`, **não validada no host até executar o build**; importação revisada e rollback disponíveis |
| RPCS3, DuckStation, PCSX2, Vita3K, Xenia Canary, xemu, Eden, Cemu, Dolphin, Azahar, mGBA, Mupen64Plus e Mesen | Gerenciamento por release/apt existente, e importação manual auditável por perfil. Não recompilados automaticamente a partir dos submódulos |

| Xbox One, Xbox Series | Sem runner suportado, instalação e execução **bloqueadas** |

Os 24 submódulos são **fontes**, não 24 pacotes prontos para rodar. Os cinco builds opcionais são *best effort* e não são parte automática do build da imagem: requerem dependências instaladas no host e podem falhar devido a mudanças upstream, submódulos internos ou bibliotecas.

## 1. Inspecionar antes de modificar

Sempre rode como usuário normal do Debian, na raiz do repositório, **sem sudo**:

```bash
python3 scripts/upstream-manager.py audit --require-checkout
python3 scripts/emulator-manager.py status
python3 scripts/emulator-manager.py deps kytyps5
python3 scripts/emulator-manager.py deps shadps4
python3 scripts/emulator-manager.py deps ppsspp
python3 scripts/emulator-manager.py deps melonds
python3 scripts/emulator-manager.py deps bsnes
```

`deps` informa comandos de build que faltam, lista sugerida de pacotes e manual oficial. **Não instala pacotes automaticamente**. Verifique a versão e a disponibilidade no Debian antes de instalar dependências no host. Alguns projetos usam submódulos Git aninhados; revise as fontes e inicialize os submódulos internos necessários antes de compilar. O gerenciador recusa checkouts com commit errado, alterações não commitadas ou submódulos internos ausentes/divergentes.

**Diagnóstico de falha no Debian.** `ninja-build` fornece `ninja`, `clang` fornece `clang` e `clang++`, e `glslang-tools` fornece `glslangValidator`. Para bsnes, `make` e `g++` existentes não são suficientes: `deps bsnes` agora também verifica os módulos `pkg-config` `gtk+-3.0` e `sdl2`; o código não instala pacotes sozinho. A lista de pacotes impressa por `deps` é uma sugestão de manutenção, não um pedido para instalar tudo sem revisar. Se um build falhar, o erro mostra as últimas linhas do log e o arquivo completo permanece em `data/emulator-manager/logs/`. 

### 1.1. Sincronizar dependências Git aninhadas (KytyPS5, shadPS4, PPSSPP)

Se o `build-all` retornar `Nested dependencies missing/mismatched`, isso significa que os **submódulos de terceiro nível pertencentes ao upstream** ainda não foram baixados. Os 24 submódulos do EmuStack já podem estar corretos; são duas camadas diferentes.

Os três upstreams possuem dezenas de dependências próprias. O comando abaixo **audita as URLs HTTPS, os gitlinks e os commits registrados** em cada `.gitmodules` antes de baixar, não segue branches nem executa o emulador. Ele só funciona com autorização explícita, limita profundidade e volume de submódulos, e não utiliza `--remote`.

```bash
python3 scripts/emulator-manager.py sync-deps kytyps5 --jobs 2 --yes-download-submodules
python3 scripts/emulator-manager.py sync-deps shadps4 --jobs 2 --yes-download-submodules
python3 scripts/emulator-manager.py sync-deps ppsspp --jobs 2 --yes-download-submodules
```

**Atenção:** isso clona muitos projetos de terceiros e pode consumir vários gigabytes e tráfego; faça apenas após revisar as URLs e licenças dos upstreams. Apenas repositórios HTTPS de `github.com` e `android.googlesource.com` são permitidos nesse sincronizador. Se houver novos hosts, mudanças em gitlinks ou profundidade excessiva, o comando **falha fechado** para revisão. A cópia temporária usada pelo build subsequente inclui o conteúdo sincronizado, mas não os metadados `.git`.

### 1.2. Resolver Qt6 do melonDS

Na execução do Debian, o CMake parou em `Qt6Config.cmake` ausente. Isso indica falta de pacotes **Qt6 de desenvolvimento** no **host**, não um problema do launcher instalado no Docker. No Debian com os pacotes correspondentes disponíveis:

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends \
    qt6-base-dev qt6-base-private-dev qt6-multimedia-dev libqt6svg6-dev \
    extra-cmake-modules libwayland-dev libcurl4-gnutls-dev
python3 scripts/emulator-manager.py deps melonds
```

A checagem de melonDS agora testa `Qt6Core`, `Qt6Widgets`, `Qt6Multimedia`, `Qt6Svg` e módulos adicionais usando `pkg-config`. Ela apenas valida pré-requisitos básicos: a compilação real é a prova final. Se houver erro de versão de CMake/Qt, **não misture repositórios Debian de versões diferentes**; examine a versão do host e os requisitos do upstream antes de prosseguir.

## 2. Compilação explícita a partir de fonte fixada

```bash
# Compilar um perfil, apenas após revisar o projeto upstream e dependências:
python3 scripts/emulator-manager.py build kytyps5 --jobs 2 --yes-run-upstream-code
python3 scripts/emulator-manager.py build shadps4 --jobs 2 --yes-run-upstream-code
python3 scripts/emulator-manager.py build ppsspp --jobs 2 --yes-run-upstream-code
python3 scripts/emulator-manager.py build melonds --jobs 2 --yes-run-upstream-code
python3 scripts/emulator-manager.py build bsnes --jobs 2 --yes-run-upstream-code
# Opcional: tentar os cinco builds em sequência e obter resultado por perfil:
python3 scripts/emulator-manager.py build-all --jobs 2 --yes-run-upstream-code
```

`build-all` é best effort: continua nos demais perfis quando uma compilação falha, emite JSON com os resultados e retorna código de erro se qualquer build falhar. Não pule a revisão de cada upstream só para economizar comandos.

O KytyPS5 pode baixar dependências de build durante a configuração CMake e exige bibliotecas auxiliares; o binário gerado sozinho não prova que o launcher será executável no contêiner. O build Docker experimental independente continua disponível, mas usa sua própria referência até ser reconciliado com o source lock.

Esses comandos **executam o sistema de build de terceiros no host**, que não é uma sandbox. Se não confiar no código, compile numa VM/host descartável em vez de executar no computador principal. O gerenciador recusa execução como root, não faz downloads de firmware/jogos e executa comandos de build com lista fixa de argumentos (sem shell).

O código-fonte é copiado para `data/emulator-manager/work/` antes do build para não modificar os submódulos. Logs de erro ficam em `data/emulator-manager/logs/`. O binário só é promovido ao perfil se o arquivo esperado realmente existir e tiver conteúdo. **Isso não comprova que o programa abra no desktop ou tenha todos os recursos auxiliares**: PPSSPP e bsnes podem exigir assets/recursos adicionais para funcionar. Teste o aplicativo real após a compilação. Nenhuma compilação deve ser considerada verde apenas porque a rotina retornou.

## 3. Importar um binário revisado, com hash obrigatório

Para perfis com runner permitido, é possível usar um executável local obtido de fonte autorizada. Exemplo para arquivo que você *já possui*, cujo hash revisou independentemente:

```bash
sha256sum /caminho/para/PPSSPPSDL
python3 scripts/emulator-manager.py install-file ppsspp /caminho/para/PPSSPPSDL \
  --binary-name PPSSPPSDL --sha256 HASH_REAL_DE_64_CARACTERES
```

O `--binary-name` é validado contra `catalog.json`; nomes arbitrários, perfil bloqueado e symlinks são rejeitados. O SHA-256 garante **igualdade com o hash fornecido**, não autenticidade do fornecedor. Não copie jogos/BIOS/firmware para `emulators/`. Arquivos que não sejam executáveis aprovados podem causar falhas, mesmo com hash válido. `install-file` não faz download, não abre o binário e não verifica a licença.

A importação usa staging no mesmo filesystem, verificação de cópia e troca por `os.replace`. Se existia um binário local no mesmo caminho, a versão antiga é preservada em `data/emulator-manager/versions/<id>/`. A imagem Docker não é alterada. O agente reconhece o binário da pasta privada na próxima consulta, mas **pare sessões em andamento antes de atualizar ou reverter**.

## 4. Atualização por versão e rollback

```bash
# Consultar novas referências oficiais, sem trocar os commits:
python3 scripts/upstream-manager.py plan --id melonds

# Pin: somente após auditoria, em branch separada:
# python3 scripts/upstream-manager.py pin melonds SHA_COMPLETO_REVISADO
# git diff --cached --submodule=log
# git commit -m "chore: update reviewed melonDS source pin"

# Construir novamente a partir do novo pin:
python3 scripts/emulator-manager.py build melonds --jobs 2 --yes-run-upstream-code

# Ver histórico, reverter ou remover somente o binário gerenciado:
python3 scripts/emulator-manager.py history melonds
python3 scripts/emulator-manager.py rollback melonds
python3 scripts/emulator-manager.py uninstall melonds
```

`rollback` recupera a última versão salva, inclusive após uma desinstalação controlada. Históricos são locais: commits Git, relatórios de build e executáveis não são a mesma coisa. O gerenciador não altera automaticamente o `source-lock.json` nem o `release-lock.json` e não faz atualização silenciosa. Para atualizar **assets da imagem Docker**, use o workflow de freeze de hashes e o rebuild revisado descrito em [Releases e atualizações](RELEASE_AND_UPDATES.md).

## 5. Estado e segurança

O inventário `status` inclui `official_release_lock` para a origem da imagem e `binary_signature` para leitura estática dos bytes ELF/possível PE/script. Nenhum dos dois comprova execução real.


```bash
python3 scripts/emulator-manager.py status ppsspp
python3 scripts/emulator-manager.py history ppsspp
./scripts/validate-project.sh
USE_NVIDIA=1 ./scripts/runtime-acceptance.sh
```

- `managed_hash_valid` certifica integridade do binário local em relação à instalação registrada; **não** certifica funcionalidade. `runtime_tested` permanece `false` até testes reais de aplicativo.
- `availability: not-checked-in-host-runtime` indica que o gerenciador não se apresenta como um monitor de jogabilidade. Consulte também os agentes e o relatório de instalação do runtime.
- `source_build: not-integrated` não significa indisponibilidade do emulador; releases oficiais ou APT podem fornecer o binário sem build fonte.
- Metadados de versões ficam em `data/emulator-manager/active/`, backups em `versions/`; **não** são compartilhados com dashboard/containers. Apenas o executável autorizado do perfil fica disponível em seu mount.
- Nunca execute compilações como root nem monte a API/porta do dashboard na rede externa para automatizar instalações. O painel continua intencionalmente sem permissões de instalação de pacotes no host.
- O rollback preserva arquivos de binário; não restaura alterações de formato de saves/configs feitas por novas versões. Use o backup de dados por perfil antes de upgrades incompatíveis.
- A exclusão/rollback não termina processos já iniciados. Encerre a sessão do emulador antes de substituir um executável.

## 6. Critérios de aceite pendentes

- Executar cada receita de build num host Debian com suas dependências reais e confirmar saída dos binários.
- Validar a presença de recursos complementares (assets) usados por cada emulador.
- Abrir a interface gráfica de cada emulador e executar um teste mínimo de conteúdo homebrew autorizado.
- Registrar drivers, versão do binário, dependências, logs, áudio, controles, save/load e encerramento.
- Exercitar rollback com o aplicativo fechado e garantir que dados persistentes permanecem corretos.

**A Fase 1 não será declarada integralmente concluída até que os builds e testes de aplicação tenham evidência no host.**
