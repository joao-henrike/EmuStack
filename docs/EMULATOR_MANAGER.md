# 🛠️ Fase 1 — Gerenciador Docker-first de emuladores

**Serialização e isolamento:** operações mutáveis usam um `flock` no estado do gerenciador, impedindo builds/rollbacks/purges simultâneos conflitantes. Para `sync-deps`, o único acesso de escrita a Git é ao checkout `third_party/<id>` selecionado e a seus metadados `.git/modules/third_party/<id>`; os outros projetos permanecem somente leitura.

> **Estado:** ciclo de código implementado na branch `fix/dashboard-degraded-startup`, sem merge em `main`. Builds reais, compatibilidade gráfica e integração com jogos **ainda dependem da rodada de testes posterior**. [Contrato e aceite](PHASE1_IMPLEMENTATION.md).

## 1. Arquitetura e fronteiras

O host só precisa do Docker Engine/CLI/Compose, checkout Git, shell e drivers/serviços gráficos necessários ao runtime. CMake, Ninja, GCC/Clang, Qt6, SDL2/3 e ferramentas de teste ficam na **imagem de builder**. Os agentes de runtime usam imagem distinta e recebem executáveis pelo mount privado `/custom-emulators:ro`, sem Docker socket nem toolchains.

O script `scripts/phase1.sh` é a interface canônica. O gerenciador Python `scripts/emulator-manager.py` é o backend executado **dentro do container**, não um comando de instalação de bibliotecas no host. O wrapper legado `scripts/build-phase1-isolated.sh` redireciona para essa interface.

Os builds dão escrita apenas a `data/emulator-manager/` e ao `data/environments/<id>/emulators/` do perfil escolhido. Jogos, BIOS, saves e a raiz do código permanecem read-only. `sync-deps` é a **exceção consentida**: permite alteração dos metadados Git e de `third_party/` para preencher submódulos pinados, nunca para seguir HEAD de branch sem revisão.

## 2. Cinco receitas de fonte pinada

| Perfil | Toolchain e recursos de build | Pacote instalado no mount do perfil |
|---|---|---|
| `kytyps5` | Clang, CMake, Ninja, Qt6 >= 6.8 | `kyty_launcher`, `kyty_emulator`, updater, bibliotecas e plugins Qt do `cmake --install` |
| `shadps4` | CMake >= 3.26, Ninja, bibliotecas nativas | `shadPS4` e dependências fornecidas pela imagem de runtime |
| `ppsspp` | CMake, Ninja, SDL3 + SDL3_ttf | `PPSSPPSDL` e diretório `assets/` do upstream |
| `melonds` | CMake, Ninja, Qt6 + SDL2 | `melonDS`, recursos embutidos e libs runtime |
| `bsnes` | Make, GTK3, SDL2 | `bsnes`, `Database/`, `shaders/` |

Todos os checkouts são conferidos contra `upstream/source-lock.json` (SHA completo e gitlink), inclusive submódulos internos. O builder não altera os commits do repo e preserva a identidade Git real do FFmpeg quando cria cópia temporária da fonte. **Isso não garante que o upstream compile sem regressões.**

Outros 13 perfis são atendidos por assets oficiais fixados em `release-lock.json`, pacotes da imagem e/ou importação explícita de arquivo revisado; não há receitas de compilação genericamente aprovadas para eles. Xbox One/Series permanecem bloqueados por inexistência de runner verificado.

## 3. Comandos canônicos

Na raiz do checkout, sem `sudo`:

```bash
# Verificar o projeto, dependências, estado e último log:
bash scripts/phase1.sh validate
bash scripts/phase1.sh test
bash scripts/phase1.sh status
bash scripts/phase1.sh deps melonds
bash scripts/phase1.sh logs melonds

# Inspecionar remotos e commits antes de baixar submódulos internos:
bash scripts/phase1.sh plan-deps shadps4
bash scripts/phase1.sh sync-deps shadps4 --yes-download-submodules --jobs 2

# Compilar somente depois de revisar os projetos upstream:
bash scripts/phase1.sh build kytyps5 --yes-run-upstream-code --jobs 2
bash scripts/phase1.sh build shadps4 --yes-run-upstream-code --jobs 2
bash scripts/phase1.sh build ppsspp --yes-run-upstream-code --jobs 2
bash scripts/phase1.sh build melonds --yes-run-upstream-code --jobs 2
bash scripts/phase1.sh build bsnes --yes-run-upstream-code --jobs 2

# Alternativa: executar todas as receitas em sequência, relatando erros separados:
bash scripts/phase1.sh build-all --yes-run-upstream-code --jobs 2
```

Os comandos de leitura/teste não têm acesso à rede. `build` e `sync-deps` usam rede apenas quando necessário aos upstreams e exigem flags explícitas. O builder é limitado a 4 CPUs, 8 GiB de RAM e 512 PIDs, com filesystem principal read-only, capabilities removidas e execução não-root. Essas restrições não substituem uma VM diante de código upstream não confiável.

## 4. Empacotamento e integridade

Cada build prepara os arquivos de runtime num pacote específico. O manager recusa symlinks, arquivos especiais, árvores maiores que 2,5 GB, número de arquivos excessivo e executável principal que não seja ELF Linux x86-64. O conteúdo e as permissões executáveis compõem um hash canônico. Só depois o pacote é instalado em:

```text
data/environments/<id>/emulators/
  <nome-do-launcher>
  .emustack-bundles/
    <hash-do-conteúdo>/
      <executável-real>
      <assets-e-plugins-da-versão>/
```

O launcher POSIX da pasta principal executa seu pacote por caminho fixo `/custom-emulators/.emustack-bundles/<hash>/...` dentro do **agente do perfil**. Trocar o launcher por `os.replace` mantém pacotes anteriores intactos; os saves ficam separados. `status` informa o hash do launcher e `bundle_hash_valid`, calculado sobre os arquivos e permissões do pacote. Se os recursos forem alterados, a validação acusa divergência.

Os bundles preservam a identidade da versão; não são garbage-collected automaticamente, porque um backup ainda pode referenciá-los. Não remova `data/emulator-manager/versions/` ou `.emustack-bundles/` para economizar espaço sem conferir o histórico.

## 5. Importação, atualização, rollback e remoção

Arquivos recebidos de fora devem ser conferidos por origem, licenças e SHA-256 antes de importar. O manager não baixa ROMs, firmware, chaves, BIOS ou executáveis arbitrários.

```bash
mkdir -p data/imports
# Coloque um executável validado no diretório acima, por exemplo: PPSSPPSDL
bash scripts/phase1.sh install-file ppsspp PPSSPPSDL SHA256_REAL_DE_64_HEX PPSSPPSDL

bash scripts/phase1.sh history ppsspp
bash scripts/phase1.sh rollback ppsspp
bash scripts/phase1.sh uninstall ppsspp
# Irreversível: após uninstall, liberar histórico/bundles gerenciados:
bash scripts/phase1.sh purge ppsspp --yes-delete-managed-backups
bash scripts/phase1.sh status ppsspp
```

`history` informa `integrity_ok` para cada backup (SHA-256 real comparado ao checksum gravado no nome). `rollback` rejeita backups adulterados e não altera a instalação ativa nesses casos. `uninstall` restaura o executável e metadados originais se falhar a persistência da remoção; `purge` verifica a integridade de backups e diretórios versionados antes de excluir qualquer arquivo. Um erro de integridade exige inspeção manual, não exclusão automática.

`install-file` aceita apenas arquivo de `data/imports` (nome sem separadores), nome de executável permitido pelo catálogo, SHA-256 correto e perfil suportado. Ele guarda um **binário avulso**: não presume recursos auxiliares e não recebe garantias de bundle.

Atualizar uma receita de fonte requer revisão de commit e gitlink em branch separada, recompilação e substituição transacional do launcher. O backup anterior guarda hash, data e proveniência; `rollback` exige que o bundle da versão anterior continue intacto e recupera também sua identidade. Desinstalação salva tombstone para permitir rollback, não termina sessões em andamento e não limpa automaticamente pacotes antigos. Para liberar espaço, **após desinstalar**, use `purge <id> --yes-delete-managed-backups`: remove apenas backups e bundles reconhecidos do perfil e impede rollback posterior; jogos, saves e BIOS não são tocados. `purge` falha se encontrar itens desconhecidos.

**Pare os emuladores antes de atualizar, reverter ou desinstalar.** A substituição do launcher não reverte mudanças em saves feitas por versões futuras; execute backup antes da atualização.

## 6. Aceitação preparada para depois da implementação

O arquivo `scripts/phase1-smoke.py` é instalado na imagem de runtime e o `scripts/phase1-acceptance.sh` inspeciona os cinco agentes pelo Docker Compose: presença do launcher, executável real, plugins/assets esperados e resolução de bibliotecas compartilhadas pelo `ldd`. O diagnóstico não roda jogos nem prova GUI. Quando iniciarmos os testes:

```bash
bash scripts/phase1.sh validate
# Após instalar os cinco pacotes e reconstruir a imagem runtime:
bash scripts/phase1-acceptance.sh
```

Também serão necessárias verificações gráficas, Vulkan/GPU, áudio, controles, logs, dados persistentes, janela real e homebrew autorizado por perfil. **Não declarar a Fase 1 funcional ou 100% validada apenas por os scripts existirem, os hashes passarem ou o CI passar.**

## 7. Evidências anteriores e limitações

- Na tentativa anterior do host, bsnes compilou e instalou um ELF diretamente; a execução gráfica não foi comprovada e a nova embalagem Docker-first ainda precisa ser executada.
- No Bookworm, KytyPS5 exigia Qt6 >= 6.8, shadPS4 CMake >= 3.26, PPSSPP SDL3; a imagem Trixie provê toolchain mais recente sem instalar bibliotecas Debian 13 no host.
- Os 24 submódulos principais são distintos dos internos: KytyPS5 (14), shadPS4 (54) e PPSSPP (28) foram sincronizados anteriormente no host.
- A imagem fixa seu digest base, mas APT sem snapshot não garante build bit a bit reprodutível.
- Driver NVIDIA e servidor gráfico/áudio permanecem dependências do host, expostas por mounts/dispositivos específicos aos agentes. O dashboard não recebe acesso ao daemon Docker.

Para detalhes de arquitetura, consulte [Docker-first](DOCKER_FIRST_ARCHITECTURE.md), [segurança](SECURITY.md), [releases](RELEASE_AND_UPDATES.md) e [contrato técnico da Fase 1](PHASE1_IMPLEMENTATION.md).
