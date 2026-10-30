# Guia do usuário — EmuStack 0.7.1

> **EMUSTACK // GAMING LAB** · [README](../README.md) · [Instalação](INSTALLATION.md) · [Guia do usuário](USER_GUIDE.md) · [Matriz de emuladores](EMULATOR_MATRIX.md) · [Segurança](SECURITY.md) · [Identidade visual](IDENTIDADE-VISUAL.md)

## O painel

- **Visão geral:** saúde do núcleo, arquivos encontrados e sessões.
- **Ambientes isolados:** estado dos 20 agentes, executável detectado, capacidade declarada e pastas exclusivas de cada perfil.
- **Sistemas originais:** perfis de boot de firmware/menu real, com pré-requisitos e limitações. A interface web não imita o dashboard do console.
- **Emuladores:** catálogo de projetos/variantes. “Launcher encontrado” não garante compatibilidade de jogos.
- **Biblioteca:** junta resultados dos agentes, mas preserva o ID do ambiente para que o mesmo arquivo ou nome em outro console não seja confundido.
- **Sessões:** logs e encerramento das sessões iniciadas pelo painel.

## Adicionar jogo

Copie o arquivo ao diretório do perfil correto, por exemplo:

```text
data/environments/rpcs3/games/
data/environments/pcsx2/games/
data/environments/dolphin/games/
```

As pastas dos jogos são montadas como somente leitura. O agente recusa caminho absoluto, travessia (`..`), symlinks e itens que não sejam arquivos regulares. A extensão é um filtro inicial, não uma confirmação de integridade ou compatibilidade.

Não coloque jogos de todos os sistemas em uma pasta comum e espere que os agentes compartilhem dados. Esse comportamento foi removido intencionalmente na 0.7.1.

## Arquivos de sistema

Coloque BIOS/boot ROM/firmware autorizado em `data/environments/<id>/bios/`. Firmware instalado pelo próprio emulador, NAND/MLC/HDD e configurações persistentes ficam no `home/` do mesmo perfil, conforme o emulador. Cada ambiente tem seu próprio HOME, mesmo quando outro perfil usa o mesmo projeto de emulação.

O projeto não baixa nem inclui ROMs, BIOS, firmware, NAND, chaves ou discos de sistema proprietários. Consulte a documentação oficial do emulador para o fluxo de instalação legal.

## Saves e configurações

`saves/` é um espaço persistente separado, mas nem todos os emuladores escrevem saves nesse caminho por padrão: alguns salvam dentro da pasta de dados do próprio emulador em `home/`. A versão 0.7.1 não promete uma localização universal para todos os sistemas.

## Boot original

A aba **Sistemas originais** é a fonte de verdade para a capacidade atual. O botão de boot só funciona quando:

1. o agente está online;
2. há um launcher compatível;
3. a estratégia de boot é suportada pelo projeto;
4. os pré-requisitos configuráveis são detectados;
5. há sessão gráfica quando o emulador exige janela.

Xbox original via xemu pode iniciar o sistema configurado, mas o EmuStack não consegue provar que o HDD tem o dashboard Microsoft retail em vez de uma alternativa aberta. PS3/XMB, PS2/BIOS, Wii Menu e Wii U Menu dependem de firmware/sistema adequado. Para PS4/PS5/Switch/Xbox 360/Xbox One, esta versão não promete boot integral do sistema/dashboard.

## Sessões e logs

As sessões ficam associadas ao ambiente. Os logs são limitados a 128 KiB por sessão e persistem em `data/environments/<id>/home/.local/state/emustack/logs/`. Use o botão **Encerrar** antes de abrir outro ambiente caso o limite global esteja atingido.
