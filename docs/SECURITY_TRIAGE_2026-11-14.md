# EmuStack — triagem inicial do inventário de segurança

**Data da revisão:** 2026-11-14  
**Imagem examinada:** `local/emustack:0.7.1`  
**Imagem imutável:** `sha256:0bc82f482d38e96f210b70dbd23353b3737575c21047ee600221f78dcf7b223e`  
**Relatório scanner:** execução CI #231, 2026-11-12; Syft 1.55.0 / Trivy 0.74.0.

## 1. Interpretação dos números

O inventário inicial (12/11) continha 560 pacotes/componentes e 401 achados em nível de pacote: 9 CRITICAL e 392 HIGH, correspondendo a **139 CVE IDs únicos** (7 CRITICAL e 132 HIGH). Após a atualização APT, a execução #233 (14/11) passou a 399 achados: 9 CRITICAL e 390 HIGH, correspondendo a **138 CVE IDs únicos** (7 CRITICAL e 131 HIGH). A execução #234 repetiu esses números e acrescentou as cadeias de dependência SPDX ao relatório.

O CVE-2026-109518 desapareceu do inventário após a imagem passar a usar APT 3.0.4; foram removidos os dois achados em nível de pacote associados a `apt` e `libapt-pkg7.0`. Os 7 CVEs únicos CRITICAL continuam pendentes de tratamento. Um mesmo CVE pode aparecer em vários pacotes binários oriundos do mesmo pacote-fonte; não contar cada linha como uma vulnerabilidade independente.

Execução #234: 175 testes Python aprovados, 20 agentes saudáveis e testes de fronteira entre agentes aprovados. A validação ocorreu em runner GitHub-hosted; GPU física, áudio, controles, BIOS/firmware e compatibilidade de jogos não foram certificados. O resultado do scanner é um snapshot de sua base de vulnerabilidades em 14/11/2026 e deve ser atualizado após cada rebuild.

## 2. Grupos inicialmente marcados CRITICAL

| Pacote binário | CVEs no relatório | Observação de triagem Debian |
|---|---|---|
| `libgdcm3.0t64` | CVE-2025-48429, CVE-2025-53618, CVE-2025-53619 | Debian Trixie consta vulnerável, sem DSA para os três no tracker consultado; versões mais novas estão listadas em forky/sid. Não atualizar isoladamente para pacote de outra suite. |
| `libmariadb3`, `mariadb-common` | CVE-2026-44172, CVE-2026-49261 | Trixie consta vulnerável sem DSA, com correção prevista em point release. A imagem contém bibliotecas cliente e metadados comuns; não contém `mariadb-server`. CVE-2026-49261 descreve especificamente `wsrep_notify_cmd`; confirmar presença do código/alcance no binário cliente antes de classificar como explorável nesta imagem. |
| `libstb0t64` | CVE-2023-45666 | Debian Trixie consta vulnerável/postponed sem DSA. O CVE envolve processamento de imagem em stb_image; tratar como relevante até concluir reachability nos consumidores da biblioteca. |
| `libxml2` | CVE-2026-6653 | Debian Trixie consta vulnerável sem DSA e classifica a questão como minor; o Trivy/NVD marcou o achado como CRITICAL. Registrar a diferença de severidade do fornecedor, sem ignorar o achado. |

## 3. Correção já aplicada

O relatório também encontrou APT 3.0.3, vulnerável ao CVE-2026-109518. O Debian corrigiu o Trixie em APT 3.0.4 (DSA-6607-1, 04/11/2026). A branch de integração passa a exigir APT 3.0.4+, desativar retries na atualização inicial e atualizar pacotes antes de instalar dependências.

## 4. Caminhos de dependência observados no SBOM

O SBOM SPDX da execução #233 contém relações `DEPENDENCY_OF`. A cadeia aponta os seguintes consumidores raiz:

- GDCM: `mupen64plus-*` → `libmupen64plus2` → `libopencv-videoio410` → `libopencv-imgcodecs410` → `libgdcm3.0t64`.
- MariaDB client: `mupen64plus-*` → `libmupen64plus2` → `libopencv-videoio410` → `libgdal36` → `libmariadb3` → `mariadb-common`.
- libstb: `dolphin-emu` → `libtinygltf6d` → `libstb0t64`.
- libxml2: múltiplos consumidores, incluindo `dolphin-emu`/`retroarch` via `libavformat61`, Mupen64Plus via `libgphoto2` e Wine via `libxkbregistry0`.

**Próxima alteração arquitetural recomendada, ainda não aplicada:** construir imagens de agente por perfil para que os pacotes APT de Dolphin e Mupen64Plus não sejam instalados em todos os 20 ambientes. Essa mudança deve vir acompanhada de SBOM/Trivy separado para cada imagem e testes de Compose que confirmem que apenas os serviços correspondentes usam os overlays. Não remover os pacotes do perfil atual sem uma imagem substituta validada.

## 4. Política de tratamento

1. Não adicionar `--ignore-unfixed`, exclusões globais ou exceções sem prazo.
2. Para cada CVE, verificar pacote binário instalado, código afetado, caminho de execução e entrada controlável.
3. Separar: vulnerabilidade aplicável; não aplicável por pacote binário/código ausente; sem correção Debian disponível; falso positivo do scanner; risco aceito com responsável e data de expiração.
4. Não importar pacotes de forky/sid para Trixie sem uma migração deliberada e testes de compatibilidade.
5. Reexecutar Syft/Trivy depois do rebuild e comparar CVE IDs únicos, não somente o número bruto de linhas.

## 5. Fontes primárias

- Debian DSA-6607-1 / CVE-2026-109518: https://lists.debian.org/debian-security-announce/2026/msg00526.html
- Debian tracker CVE-2025-48429: https://security-tracker.debian.org/tracker/CVE-2025-48429
- Debian tracker GDCM (inclui CVE-2025-53618 e CVE-2025-53619): https://security-tracker.debian.org/tracker/source-package/gdcm
- Debian tracker CVE-2026-44172: https://security-tracker.debian.org/tracker/CVE-2026-44172
- Debian tracker CVE-2026-49261: https://security-tracker.debian.org/tracker/CVE-2026-49261
- Debian tracker libstb: https://security-tracker.debian.org/tracker/source-package/libstb
- Debian tracker CVE-2026-6653: https://security-tracker.debian.org/tracker/CVE-2026-6653

**Limite:** esta é uma triagem inicial baseada no SBOM/Trivy da imagem CI. Não substitui análise de reachability, revisão dos binários, teste em host real ou parecer de segurança independente.
