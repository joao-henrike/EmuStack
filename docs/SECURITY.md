# Modelo de segurança — EmuStack 0.7.1

## Defaults

- Dashboard publicado somente em `127.0.0.1:8765`; não foi projetado para acesso remoto/LAN.
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

Docker compartilha o kernel do host. Não é uma sandbox de alta garantia para executar código deliberadamente malicioso. A camada de programas dos emuladores está presente na imagem comum e somente leitura; o isolamento principal é de dados, mounts, rede e agente/controlador, não uma VM por console. Um bug no dashboard poderia alcançar os endpoints permitidos dos agentes; mantenha o dashboard local e o segredo privado.

Se o host habilitar GPU, X11/XWayland, áudio ou um controle, o contêiner recebe acesso ao recurso correspondente. X11 em particular pode expor a sessão gráfica ao cliente. Não habilite essas passagens para binários nos quais não confia.

## Dados privados e firmware

Não versione nem publique BIOS, firmware, chaves, NAND, HDDs ou saves sensíveis. O projeto não inclui tais arquivos. Não recomendo expor o painel com reverse proxy ou encaminhamento de porta sem autenticação, proteção CSRF, limitação de taxa e revisão completa adicional.

## Verificação

A suite estática testa allowlists, validação de caminhos, composição das redes e separação de mounts. Isso não substitui inspeção real de `docker inspect`, testes de conectividade entre contêineres, build de imagem, teste de GPU ou execução de sistema/jogo na máquina-alvo.
