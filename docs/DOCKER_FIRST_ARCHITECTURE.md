# 🐳 Princípio Docker-first do EmuStack

**Serialização e isolamento:** operações mutáveis usam um `flock` no estado do gerenciador, impedindo builds/rollbacks/purges simultâneos conflitantes. Para `sync-deps`, o único acesso de escrita a Git é ao checkout `third_party/<id>` selecionado e a seus metadados `.git/modules/third_party/<id>`; os outros projetos permanecem somente leitura.

**Decisão operacional aplicada à Fase 1:** somente o estado do manager e o subdiretório `emulators/` do perfil em alteração são graváveis no builder. `data/` permanece read-only em geral, protegendo jogos/saves/BIOS; `sync-deps` constitui exceção explícita para gravar Git/submódulos. Veja [escopo completo](PHASE1_IMPLEMENTATION.md).

> Regra de engenharia: não instalar ferramentas de compilação ou bibliotecas de emuladores no host quando puderem existir numa imagem Docker pinada, auditável e descartável.

## Separação de responsabilidades

| Componente | Local | Política |
|---|---|---|
| Emuladores, APIs, dashboard e proxy | 20 agentes + serviços Compose | Processos da aplicação ficam em containers, com redes e mounts restritos por perfil |
| CMake, Clang, GCC, Ninja, Qt, SDL2/3, FFmpeg de build, pkg-config | Imagem dedicada `scripts/phase1-builder/Dockerfile` | Nunca instalar no host só para compilar o EmuStack |
| Build e testes do gerenciador, dependências, validação estática | `bash scripts/phase1.sh` | Mesma toolchain Trixie para todos os perfis; leitura de fontes e escrita apenas em `data/` |
| Jogos, BIOS/firmware autorizados, saves, configs, logs, binários locais | `data/environments/<id>/` ou `data/emulator-manager/` | Persistência por volumes; **nunca gravar na imagem**; backups independentes |
| Kernel Linux, driver de GPU, Docker Engine/CLI/Compose, hardware e sessão gráfica/áudio | Host | Interface inevitável com hardware; NVIDIA Container Toolkit quando necessário |
| Git e comandos POSIX de bootstrap | Host (ainda utilizados por checkout e scripts legados) | Manter apenas as ferramentas mínimas do sistema para obter/operar o projeto |

**Limite físico:** containers compartilham o kernel do host. Instalar CUDA/Qt/SDL dentro da imagem não substitui driver NVIDIA do host, kernel DRM, servidor X11/Wayland, PipeWire/PulseAudio ou a ponte com controle USB/Bluetooth. O host expõe apenas os sockets/devices autorizados aos containers necessários. Não disponibilizar `/var/run/docker.sock` ao dashboard ou aos agentes.

## CLI padronizada — Fase 1

Na raiz do repo, o host só executa **Bash + Docker**; Python, Node, CMake, Qt, SDL e ferramentas de build são fornecidos pela imagem de build.

```bash
# Validar o projeto, incluindo testes Python/JavaScript/shell, sem Python/Node no host:
bash scripts/phase1.sh validate

# Testes focados no manager sem acesso de rede:
bash scripts/phase1.sh test

# Inspecionar um perfil ou todos os perfis sem rede:
bash scripts/phase1.sh deps melonds
bash scripts/phase1.sh status

# Compilar somente com consentimento explícito e upstream revisado:
bash scripts/phase1.sh build melonds --yes-run-upstream-code --jobs 2
bash scripts/phase1.sh build bsnes --yes-run-upstream-code --jobs 2
bash scripts/phase1.sh build ppsspp --yes-run-upstream-code --jobs 2
bash scripts/phase1.sh build shadps4 --yes-run-upstream-code --jobs 2
bash scripts/phase1.sh build kytyps5 --yes-run-upstream-code --jobs 2
```

`scripts/build-phase1-isolated.sh` permanece como **alias legado** para `scripts/phase1.sh build`, sem implementar outra toolchain. `build` tem rede Docker bridge para downloads exigidos pelos upstreams; `status`, `deps`, `test` e `validate` usam `--network none`. Sempre confirme a origem dos códigos-fonte e libs prebuilt antes de executar. A imagem Trixie fixa o digest base mas, por enquanto, **pacotes APT não estão congelados por snapshot**. Não declare build bit a bit reproduzível.

Os builds são limitados a quatro CPUs, 8 GiB de RAM e 512 processos, com `cap_drop=ALL`, `no-new-privileges`, execução não-root e filesystem read-only fora do mount `data/` e do tmpfs. A CLI de host confia no Docker Engine e portanto **acesso ao daemon Docker é altamente privilegiado**; não dê essa permissão a aplicações web ou usuários não confiáveis.

### Arquitetura de execução

```text
Host Debian Linux
├── Docker Engine + Compose (+ GPU toolkit/driver quando necessário)
├── Git checkout e diretório data/ (persistente)
├── Contêiner builder Trixie (temporário; toolchain/Qt/SDL/FFmpeg)
│   ├── /workspace            (fonte somente leitura)
│   ├── /workspace/data       (logs, versões, binários por perfil)
│   └── /tmp                  (staging e caches descartáveis)
└── EmuStack Compose
    ├── Dashboard + proxy em 127.0.0.1
    └── 20 agentes isolados
        ├── /custom-emulators (binários do perfil, somente leitura)
        └── mounts exclusivos: games:ro, bios:ro, saves:rw, home:rw
```

## Estado de migração e dívida técnica

- **Gerenciamento de espaço:** `purge` somente apaga históricos e pacotes gerenciados após `uninstall` e com autorização explícita; as demais pastas de `data/` são preservadas.
- **Feito:** 20 agentes e dashboard em Compose; builder da Fase 1 para os cinco perfis; `status`, `deps`, `test` e `validate` dentro do Docker; sem necessidade de CMake, Qt ou SDL no host para essas operações.
- **Ainda legado:** `scripts/host-setup.sh` usa Python 3 para gerar o override de GUI/áudio, e `scripts/build-and-audit.sh` e `scripts/host-doctor.py` ainda contêm comandos Python do host. Não afirmar que a migração integral do bootstrap/runtime tooling esteja concluída até trocar esses pontos.
- **Pendente:** confirmar o build real dos cinco perfis na imagem, empaquetar todos os assets/libs para execução, validar GUI/áudio/GPU e ROMs de teste autorizadas; testar o ciclo update/rollback end-to-end.
- **Não fazer:** instalar Debian 13 por cima do Debian 12; misturar repos APT do host; publicar dashboard em interface externa; dar socket Docker a agentes; copiar firmwares ou ROMs de terceiros para a imagem.

Para uso geral, consulte [Instalação](INSTALLATION.md), [Gerenciador](EMULATOR_MANAGER.md), [Segurança](SECURITY.md) e [Aceitação](LOCAL_ACCEPTANCE.md).
