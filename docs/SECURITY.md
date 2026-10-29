# Modelo de segurança — EmuStack 0.7.1

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
- `read_only`, `cap_drop: ALL`, `no-new-privileges`, `tmpfs` e limites de recursos são ativados no contêiner.
- Mapeamento de controle e integração gráfica/audio são explícitos; nenhum `/dev/input` inteiro é passado por padrão.
- `.env` contém vinte tokens distintos (um por agente) e é gravado com permissões `0600`; nunca o versione nem publique.

## Limites do modelo

Docker compartilha o kernel do host. Não é uma sandbox de alta garantia para executar código deliberadamente malicioso. A camada de programas dos emuladores está presente na imagem comum e somente leitura; o isolamento principal é de dados, mounts, rede e agente/controlador, não uma VM por console. O dashboard é o único componente nas redes dos agentes e tem credenciais de todos eles. O filtro de origem reduz o risco de um agente comprometido usar endpoints mutáveis do dashboard; a aceitação tenta reproduzir esse caminho a partir dos 20 agentes. Isso não transforma Docker em fronteira de VM e não protege contra invasor com privilégios no host ou vulnerabilidades do kernel.

Se o host habilitar GPU, X11/XWayland, áudio ou um controle, o contêiner recebe acesso ao recurso correspondente. X11 em particular pode expor a sessão gráfica ao cliente. Não habilite essas passagens para binários nos quais não confia. O overlay opcional `compose.nvidia.yaml` não inclui `env-xbox-one` nem `env-xbox-series`, pois esses perfis estão declarados sem runner suportado; a configuração base não injeta a GPU NVIDIA por padrão. Antes de adicionar novos serviços ao overlay, confirme que o perfil possui um runner e que a aceleração precisa ser exposta.

## Dados privados e firmware

Não versione nem publique BIOS, firmware, chaves, NAND, HDDs ou saves sensíveis. O projeto não inclui tais arquivos. Não recomendo expor o painel com reverse proxy ou encaminhamento de porta sem autenticação, proteção CSRF, limitação de taxa e revisão completa adicional.

## Verificação

A suite estática testa allowlists, caminhos, IPAM e separação de mounts. A aceitação de runtime verifica IPs/mounts reais e tenta POSTs com cabeçalhos forjados a partir de cada agente; isso precisa passar em execução Docker real. Não substitui revisão independente, testes de GPU ou execução de jogos na máquina-alvo.
