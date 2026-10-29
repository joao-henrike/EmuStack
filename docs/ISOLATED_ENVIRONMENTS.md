# 🔒 Arquitetura dos ambientes isolados

## 🎯 Objetivo e limite da separação

Cada ID do catálogo tem um agente e uma raiz persistente exclusivos. Os ambientes compartilham o kernel Linux do host e a camada de programas instalada na imagem comum, mas não recebem bind mounts graváveis das bibliotecas dos outros perfis. Trata-se de isolamento de contêiner, não de uma VM de console com kernel e hardware virtuais independentes.

## 🧩 Classes de serviço

| Serviço | Responsabilidade | Dados/autoridade |
|---|---|---|
| `dashboard` | UI/API e coordenação dos agentes | Publica apenas `127.0.0.1:8765`; guarda tokens dos agentes, mas não monta bibliotecas persistentes nem socket Docker. |
| `env-<id>` | Agente de controle por perfil | Recebe apenas os mounts desse perfil; participa de uma rede interna exclusiva. |
| `emustack` | CLI/relatórios/manutenção | Rede de gerenciamento; não recebe as raízes persistentes de todos os consoles como volumes graváveis. |
| Imagem de runtime | Programas de emulação instalados no build | Camada comum, imutável para os serviços de runtime; cada override local é específico do ambiente. |

## 📂 Política de mounts

Cada agente recebe os destinos correspondentes a:

| Pasta do host | Destino lógico | Modo | Conteúdo |
|---|---|---|---|
| `data/environments/<id>/games/` | `/games` | Somente leitura | Jogos/arquivos de conteúdo daquele perfil. |
| `data/environments/<id>/bios/` | `/bios` | Somente leitura | Dumps/boot files colocados pelo usuário. |
| `data/environments/<id>/saves/` | `/saves` | Gravável | Área de saves, quando suportada/configurada. |
| `data/environments/<id>/home/` | `/home/emu` | Gravável | Configurações, estado persistente, NAND/MLC/HDD conforme o emulador. |
| `data/environments/<id>/emulators/` | Override do perfil | Somente leitura no contrato do runtime | Binários locais de override reconhecidos pelo catálogo. |

O mapeamento específico de cada serviço é definido em `compose.yaml`; a tabela descreve o modelo de dados e não substitui a inspeção da configuração efetiva. O dashboard não monta esses cinco diretórios. O setup e o storage recusam symlinks nas raízes que poderiam fazer dois perfis apontarem para os mesmos dados.

## 🌐 Política de rede e identidade

- Cada agente tem uma bridge `internal: true` exclusiva e não participa diretamente da rede de outro perfil.
- As redes usam IPAM estático no intervalo padrão `172.28.1.0/24` até `172.28.20.0/24`.
- Em cada rede, gateway é `.1`, agente é `.2` e dashboard é `.3`.
- A allowlist de clientes confiáveis do dashboard contém os gateways definidos, não os endereços dos agentes.
- Cada agente tem um token exclusivo gerado pelo `host-setup.sh`, armazenado no `.env` local com permissão restrita.
- Os agentes não têm egress externo por padrão; o dashboard não é um proxy genérico para essa rede.

Se a LAN/VPN do host se sobrepõe a `172.28.0.0/16`, planeje uma faixa sem conflito e altere **em conjunto** IPAM, gateways, IPs e allowlist. Não altere apenas uma das partes nem exponha o dashboard por reverse proxy.

## 🛡️ Hardening de runtime

O Compose configura, quando aplicável, filesystem root read-only, capabilities removidas, `no-new-privileges`, `tmpfs` e limites de CPU/memória/PIDs. A API valida ID e parâmetros e não aceita binários arbitrários, comandos shell ou paths fora do escopo esperado. As pastas de jogo/BIOS ficam read-only dentro do agente.

Display/X11/XWayland, GPU, áudio e dispositivo de input são integrações com o host. São opt-in e ampliam a superfície de ataque; forneça apenas o recurso necessário. X11 pode possibilitar acesso amplo à sessão gráfica dependendo das permissões/configuração.

## ⚠️ O que este desenho não promete

- Não resiste a um host/root já comprometido nem corrige vulnerabilidades do kernel.
- Não torna Docker equivalente a uma VM nem elimina riscos de executar emuladores de terceiros.
- Não garante ausência absoluta de bugs em mounts, redes, API ou drivers.
- Não autentica a licença nem a autenticidade de jogos/BIOS/firmware.
- Não prova desempenho, GUI, áudio, controle ou boot de jogo sem testes correspondentes.
- O dashboard coordena os agentes e conhece os tokens; por isso deve permanecer local e ser mantido atualizado.

## ✅ Como verificar a separação

```bash
docker compose ps
./scripts/runtime-acceptance.sh
docker network ls
docker inspect <nome-ou-id-do-container>
```

Use os nomes reais listados por `docker compose ps`; a aceitação efetua checks mais detalhados de rede, IPAM, mounts e tentativas de chamadas protegidas. Se algum check falhar, não declare isolamento validado. Consulte [Aceitação local](LOCAL_ACCEPTANCE.md) e [Segurança](SECURITY.md).
