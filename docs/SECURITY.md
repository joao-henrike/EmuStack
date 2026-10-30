# Modelo de segurança — EmuStack 0.7.1

> **EMUSTACK // GAMING LAB** · [README](../README.md) · [Instalação](INSTALLATION.md) · [Guia do usuário](USER_GUIDE.md) · [Matriz de emuladores](EMULATOR_MATRIX.md) · [Segurança](SECURITY.md) · [Identidade visual](IDENTIDADE-VISUAL.md)

## Defaults

- Dashboard publicado somente em `127.0.0.1:8765`; não foi projetado para acesso remoto/LAN.
- Requisições do dashboard (exceto uma resposta mínima de saúde) e todas as mutações validam o IP TCP de origem: loopback no modo host e gateways `.1` explicitamente allowlisted no Compose. Os agentes usam IP `.2` e o dashboard `.3`; `Host`, `Origin` e cabeçalhos customizados não são tratados como autenticação.
- Os subnets padrão são `172.28.1.0/24` a `172.28.20.0/24`. Se a rede/VPN local já usa essa faixa, ajuste todos os subnets, gateways, IPs e a allowlist em conjunto. Não exponha o dashboard por reverse proxy.
- Nenhum socket do Docker é montado em dashboard, agentes ou CLI.
- O dashboard não monta dados persistentes de consoles.
- Cada agente tem mounts exclusivos para `games` (ro), `bios` (ro), `saves` (rw), `home` (rw) e `emulators` (ro).
- Cada ambiente usa sua própria rede `internal: true`; agentes irmãos não estão conectados à rede uns dos outros e não têm saída externa por padrão.
- Agentes validam o token, allowlist de IDs e parâmetros; não aceitam shell ou caminhos de binário arbitrários via API.
- Caminho de jogo deve ser relativo e fica confinado a `/games`; symlinks e travessias são rejeitados.
- `read_only`, `cap_drop: ALL`, `no-new-privileges`, `tmpfs` e limites de CPU/memória/PIDs são ativados nos contêineres; a aceitação verifica os valores efetivos do Docker.
- Logs de contêiner usam `json-file` com rotação finita (`max-size: 10m`, `max-file: 3`) para limitar crescimento local de logs.
- Mapeamento de controle e integração gráfica/audio são explícitos; nenhum `/dev/input` inteiro é passado por padrão.
- `.env` contém vinte tokens distintos (um por agente) e é gravado com permissões `0600`; nunca o versione nem publique.

## Limites do modelo

Docker compartilha o kernel do host. Não é uma sandbox de alta garantia para executar código deliberadamente malicioso. A camada de programas dos emuladores está presente na imagem comum e somente leitura; o isolamento principal é de dados, mounts, rede e agente/controlador, não uma VM por console. O dashboard é o único componente nas redes dos agentes e tem credenciais de todos eles. O filtro de origem reduz o risco de um agente comprometido usar endpoints mutáveis do dashboard; a aceitação tenta reproduzir esse caminho a partir dos 20 agentes. Isso não transforma Docker em fronteira de VM e não protege contra invasor com privilégios no host ou vulnerabilidades do kernel.

Se o host habilitar GPU, X11/XWayland, áudio ou um controle, o contêiner recebe acesso ao recurso correspondente. X11 em particular pode expor a sessão gráfica ao cliente. Não habilite essas passagens para binários nos quais não confia. O overlay opcional `compose.nvidia.yaml` não inclui `env-xbox-one` nem `env-xbox-series`, pois esses perfis estão declarados sem runner suportado; a configuração base não injeta a GPU NVIDIA por padrão. Antes de adicionar novos serviços ao overlay, confirme que o perfil possui um runner e que a aceleração precisa ser exposta.

## SBOM e varredura de vulnerabilidades

A CI gera um SBOM SPDX JSON da imagem de runtime que acabou de construir e publica o JSON completo da varredura de vulnerabilidades OS/library de severidade **HIGH/CRITICAL**. A aceitação de runtime também valida limites efetivos de CPU/memória/PIDs, a política de restart e rotação de logs; no CI, há um teste opt-in de recuperação forçada de um agente isolado. As versões de Syft e Trivy, os URLs de release e os SHA-256 esperados ficam em `supply-chain-tools.json`; `scripts/supply-chain-scan.sh` verifica o hash do arquivo baixado e a versão reportada antes de executar cada ferramenta.

A política inicial é `report-only` para achados: o inventário precisa ser revisto antes de tornar achados um gate, sem ocultar vulnerabilidades sem correção conhecida. A CI falha se download, hash/versão, geração do SBOM, execução do scanner ou leitura do JSON falharem. Não falha apenas pela presença de CVEs neste primeiro baseline. Para cada achado HIGH/CRITICAL, revisar pacote afetado, versão corrigida, alcançabilidade no produto e risco real; exceções aceitas precisam de justificativa e data de expiração. Não transformar esse modo inicial em aceitação permanente sem triagem.

Os artefatos são associados ao commit da execução: `emustack-image.spdx.json`, `emustack-trivy-vulnerabilities.json`, `supply-chain-summary.md`, `supply-chain-tool-lock.json` e os logs de versão das ferramentas. A inteligência de vulnerabilidades do Trivy é atualizada entre execuções, então resultados de runs diferentes não são comparáveis sem registrar a data/versão do banco. O relatório não prova que todos os binários upstream foram instalados: na CI os downloads de emuladores permanecem desligados, embora os pacotes Debian presentes na imagem sejam escaneados.

## Dados privados e firmware

Não versione nem publique BIOS, firmware, chaves, NAND, HDDs ou saves sensíveis. O projeto não inclui tais arquivos. Não recomendo expor o painel com reverse proxy ou encaminhamento de porta sem autenticação, proteção CSRF, limitação de taxa e revisão completa adicional.

## Verificação

A suite estática testa allowlists, caminhos, IPAM e separação de mounts. A aceitação de runtime verifica IPs/mounts reais e tenta POSTs com cabeçalhos forjados a partir de cada agente; isso precisa passar em execução Docker real. Não substitui revisão independente, testes de GPU ou execução de jogos na máquina-alvo.
