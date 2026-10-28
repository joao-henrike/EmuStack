# EmuStack 0.7.1 — Relatório de arquitetura, alterações e testes

**Data:** 28 de outubro de 2026  
**Resultado:** testes locais automatizados aprovados; runtime Docker e boot real não executados neste ambiente.

## Resumo

EmuStack 0.7.1 entrega 20 perfis de runtime isolados e 21 entradas de sistema/menu documentadas. A versão melhora a separação das pastas, a prevenção de symlinks em raízes de ambiente, o armazenamento, o diagnóstico do host, a declaração de capacidade, a rastreabilidade de releases e a validação do runtime.

Isto não equivale a 20 consoles integralmente emulados. O dashboard é um plano de controle; os sistemas originais só podem iniciar se o emulador upstream suportar esse caminho e os arquivos válidos do usuário estiverem configurados. Sistemas sem esse suporte permanecem explicitamente não suportados.

## Alterações implementadas

### Ambientes e isolamento

- 20 IDs correspondem exatamente entre `catalog.json` e `environments.json`.
- Cada agente tem diretórios próprios `games/`, `bios/`, `saves/`, `home/` e `emulators/`.
- Cada agente recebe uma bridge interna exclusiva; o dashboard se conecta aos agentes para orquestrá-los.
- O dashboard não monta as pastas persistentes dos ambientes nem o socket Docker.
- Os ambientes usam root filesystem read-only, `cap_drop: ALL`, `no-new-privileges`, limites configuráveis de CPU/RAM/PIDs e tokens individuais.
- O setup e a ferramenta de armazenamento recusam raízes/paths de mount que sejam symlinks de forma a redirecionar um ambiente para outro.

### Perfis e capacidade de boot

- Perfis antigos redundantes ou não executáveis foram removidos: `sharpemu`, `ps5pcem`, `windurango`, `xwine1` e `xenia-edge`.
- Adicionados perfis para DuckStation/PS1, PPSSPP/PSP e Vita3K/PS Vita.
- Xbox One e Xbox Series são placeholders bloqueados, sem comando de lançamento; não foi criada interface falsa ou executável fictício.
- PS1, PS2, PS3, Wii e Wii U têm rotas condicionais de BIOS/menu. O PSP ganhou rota VSH/XMB com `PPSSPP --vsh`, explicitamente experimental e dependente de firmware e versão compatível.
- O Xbox original requer configuração do xemu e uma confirmação explícita da imagem HDD ligada ao SHA-256 e ao caminho montado. Essa confirmação é uma declaração do operador e **não** prova automaticamente o conteúdo interno do HDD.
- PS4/PS5, Xbox 360 dashboard, Xbox One/Series e Nintendo Switch HOME Menu não são apresentados como boot integral de sistema original.

### Armazenamento e diagnóstico

- `scripts/manage-storage.py`: `init`, `inspect`, `backup`, `restore`, `create-disk`.
- Snapshots contêm manifesto, hashes SHA-256, limites de tamanho/quantidade e validação de paths. Restore verifica a identidade do ambiente, rejeita links/especiais e conserva o estado anterior para rollback.
- A criação `qcow2`/`raw` gera somente disco de dados vazio; não instala OS, BIOS, jogos ou dashboard.
- `scripts/host-doctor.py` faz diagnóstico de Docker/Compose, memória, GPU NVIDIA, Vulkan, display, áudio, controles e `qemu-img`.
- `scripts/runtime-acceptance.py` verifica serviços, saúde, redes, mounts, flags de hardening, bloqueio de boot não suportado e probes opcionais de X11/XWayland, áudio Pulse, Vulkan/GPU real versus renderer de software e dispositivo de controle explicitamente mapeado. Grava um relatório sem tokens em `data/runtime-acceptance.json`.

### Reprodutibilidade

- O Dockerfile usa o digest multi-arquitetura da imagem oficial Debian `trixie-slim` observado em 28-10-2026: `sha256:89c1ea91e897f0fe0a3731595330bc45b8bdef4047464a07116f891a94054b31`. Referência oficial: https://hub.docker.com/_/debian/tags/ .
- O build do KytyPS5 está restrito a uma tag e checa um prefixo de commit esperado.
- `APT_SNAPSHOT_TIMESTAMP=YYYYMMDDTHHMMSSZ` permite resolver pacotes usando um snapshot Debian datado. Isso congela também as correções de segurança do snapshot, por isso deve ser atualizado após revisão de patches.
- `FREEZE_RELEASE_LOCK=1` tenta capturar hashes dos assets oficiais realmente obtidos e reconstruir com um lock estrito.
- O `release-lock.json` entregue está no modo permissivo, sem assets upstream hash-pinned ainda. É necessário executar o build online no host para obter os assets disponíveis e então congelá-los. Não se afirma que isso já foi concluído.
- Não há garantia de build bit-a-bit idêntico em toda arquitetura ou versão de Docker/BuildKit. Releases experimentais, pacotes APT indisponíveis e builds upstream podem falhar; o relatório de instalação deve ser consultado.

## Resultados de validação executada

| Verificação | Resultado |
|---|---:|
| Testes unitários/regressão Python | **75/75 passaram** |
| Casos de recomendação de lançamento JavaScript | **13/13 passaram** |
| Verificações estáticas da UI de sistemas originais | **11 assertions passaram** |
| Compilação sintática Python | Passou |
| Sintaxe shell dos scripts | Passou |
| Parse YAML do `compose.yaml` | Passou; 22 serviços definidos |
| Parse YAML do `compose.nvidia.yaml` | Passou; 20 overlays de agente |
| Helpers de acceptance/probes | Passou; cenários simulados de integração disponível/ausente |
| IDs catálogo ↔ ambientes | 20/20 iguais e únicos |
| Alvos de sistema/menu documentados | 21 |
| Referências aos antigos perfis duplicados no catálogo/documentação | Nenhuma |

## Não executado / limitações externas

O ambiente de trabalho não contém `docker`, `podman` nem `buildah`. Portanto, não foi possível executar `docker compose config`, construir a imagem real, resolver/baixar ativos upstream, verificar a saúde dos contêineres, nem executar `scripts/runtime-acceptance.sh` aqui. O `runtime-acceptance.py` foi coberto com testes unitários simulados para caminhos de sucesso/falha, mas os probes dependem de execução real dentro dos contêineres no host. O parse YAML, a sintaxe do Dockerfile e os testes unitários não substituem essas etapas.

Também não foi possível provar a execução com sua GPU, áudio, controle, jogos, firmware, NAND/MLC/HDD ou interfaces originais no seu computador. São necessários testes no Debian host com Docker Engine + Compose v2 e arquivos próprios legalmente utilizáveis.

## Próximos comandos no Debian do usuário

```bash
chmod +x scripts/host-setup.sh scripts/build-and-audit.sh scripts/validate-project.sh scripts/runtime-acceptance.sh
./scripts/host-setup.sh
./scripts/validate-project.sh
./scripts/build-and-audit.sh
./scripts/runtime-acceptance.sh
```

Para tentar congelar hashes de releases com build online:

```bash
FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh
```

Modo APT com snapshot fixo (a data de exemplo precisa ser atualizada após revisão das atualizações de segurança):

```bash
APT_SNAPSHOT_TIMESTAMP=20261027T000000Z FREEZE_RELEASE_LOCK=1 ./scripts/build-and-audit.sh
```

O aceite de runtime verifica topologia Docker, endpoints e, quando configurados, conectividade básica de display/áudio/Vulkan/controle. Não verifica entradas físicas do controle nem compatibilidade universal de jogos; o boot real de cada sistema ainda exige teste individual por perfil.
