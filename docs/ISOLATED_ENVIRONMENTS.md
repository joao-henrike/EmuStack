# Arquitetura dos ambientes isolados — 0.7.1

## Objetivo

Cada perfil do catálogo tem um contêiner/agente próprio e uma raiz de dados exclusiva. O dashboard é um plano de controle; ele não monta as bibliotecas, BIOS, saves ou HOME dos consoles. O serviço `emustack` de CLI também não recebe os dados persistentes dos ambientes.

## Limite de confiança

- `dashboard`: publica apenas `127.0.0.1:8765`, conecta-se às redes dos agentes e usa os 20 segredos `EMUSTACK_AGENT_TOKEN_<ID>` (um token distinto por agente); não tem socket Docker nem mounts de dados do usuário.
- `env-<id>`: recebe cinco mounts exclusivos (`games`, `bios`, `saves`, `home`, `emulators`) e participa de somente uma rede interna (`env-<id>-net`). Os outros agentes não participam dessa rede.
- `emustack` CLI: usa uma rede interna de gerenciamento e não monta os dados dos consoles.
- Imagem de runtime: os executáveis de emuladores instalados no build fazem parte de uma camada comum e imutável da imagem; os contêineres não compartilham volume gravável para esses programas. Cada ambiente pode ter binários de override próprios em `data/environments/<id>/emulators/`.
- Dispositivos: X11/XWayland, GPU, áudio e controle não são dados de console e podem ser compartilhados com autorização explícita do host. Isso amplia a superfície de ataque e deve ser evitado em ambientes não confiáveis.

## Política de dados

`cross_environment_storage = denied by default`. Não há bind mount de uma raiz de ambiente em outro ambiente. `games` e `bios` são read-only no contêiner; `saves` e `home` são graváveis e persistentes. Os logs ficam em `home/.local/state/emustack/logs/`. Não existe migração automática das pastas compartilhadas de versões anteriores.

## Política de rede

Cada rede `env-<id>-net` usa `internal: true`. O agente não recebe interface direta para qualquer rede de outro ambiente e não tem egress externo por padrão. O dashboard se conecta a todas essas redes para controlar os agentes, mas não oferece proxy genérico: usa um conjunto pequeno de endpoints e os IDs são validados contra `environments.json`.

O token de 256 bits é criado por `scripts/host-setup.sh` e guardado em `.env` com permissões restritas. As rotas de ação exigem `X-EmuStack-Agent-Token`, fazem validação do ID/sistema e não aceitam binário, shell ou lista de argumentos arbitrária fornecida pelo navegador. O endpoint de saúde só revela status básico dentro da rede correspondente.

## Defesa no contêiner

Os serviços de runtime usam `read_only: true`, `cap_drop: ALL`, `no-new-privileges`, limites de CPU/RAM/PIDs e `tmpfs` para temporários. Só um dispositivo de controle explicitamente selecionado pode ser mapeado. A integração gráfica/audio também é opt-in.

## Auditoria de saves e dados persistentes

EmuStack mantém dois diretórios persistentes por ambiente: `home` (montado em `/home/emu`) e `saves` (montado em `/saves`). Alguns upstreams usam subpastas próprias em `home`; outros gravam ao lado do arquivo do jogo ou dentro de armazenamento virtual/NAND. O projeto **não cria symlinks genéricos nem move saves automaticamente**, porque isso pode corromper dados, quebrar a configuração ou tentar gravar no mount `/games`, que é somente leitura.

O contrato conservador está em `save-paths.json`; ele distingue caminhos documentados de candidatos que ainda exigem validação no runtime. Para auditar a instalação local sem abrir nem listar nomes/conteúdos dos arquivos:

```bash
python3 scripts/audit-save-layout.py
python3 scripts/audit-save-layout.py --strict
python3 scripts/audit-save-layout.py --output /tmp/emustack-save-layout-audit.json
```

A auditoria é somente de leitura por padrão. Ela informa diretórios candidatos observados, contagem agregada de arquivos/tamanho, entradas symlink ignoradas e perfis que precisam de validação manual. O resultado não registra nomes de arquivos nem caminhos absolutos do host. `--strict` retorna erro se detectar caminhos inseguros/symlinks no caminho auditado; `--output` só grava o relatório porque essa saída foi solicitada explicitamente.

Para declarar um caminho funcional, ainda é necessário iniciar o emulador com conteúdo de teste autorizado, gravar um save, fechar o processo, confirmar que o arquivo foi persistido e carregá-lo novamente. A presença de uma pasta, por si só, não demonstra que aquele build utiliza o caminho.

## O que isso não promete

É isolamento por contêiner Linux, não virtualização completa da placa-mãe de um console. Todos os agentes executam a mesma imagem de programas, ainda que seus dados persistentes sejam separados. O dashboard é privilegiado *logicamente* como orquestrador e, se comprometido, poderia enviar solicitações aos agentes; por isso deve permanecer local. O processo do emulador dentro de um contêiner também pode ter acesso a dispositivos de infraestrutura concedidos, como display/GPU.

Os checks de unidade e de configuração não provam isolamento em runtime. Para declarar validado em uma máquina real, é necessário construir a imagem, conferir redes/mounts com Docker, testar que cada agente só vê seus próprios diretórios, verificar display/áudio/GPU e iniciar um sistema/jogo legalmente fornecido.
