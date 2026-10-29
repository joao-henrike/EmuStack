# 🖥️ Sistemas originais, BIOS e menus reais

EmuStack **não desenha réplicas HTML** dos dashboards dos consoles. Quando há uma rota, o agente chama um emulador e a tela deve vir do sistema efetivamente emulado. Quando não há suporte conhecido, o perfil fica manual, indisponível ou bloqueado.

## 📁 Onde ficam os arquivos

Cada perfil deve manter seu próprio estado:

```text
data/environments/<id>/bios/   # dumps de BIOS/boot/firmware quando lidos deste caminho
data/environments/<id>/home/   # configs e estado persistente, inclusive NAND/MLC/HDD quando aplicável
data/environments/<id>/saves/  # saves quando o emulador usa este diretório
```

Não compartilhe essas pastas entre ambientes via symlinks, nem use uma pasta global para todos os sistemas. O container vê o HOME do perfil em `/home/emu`.

## 🎮 Rotas de boot e pré-requisitos

### PlayStation 3 — RPCS3 / VSH-XMB
A rota procura o módulo VSH instalado dentro da configuração do RPCS3 no HOME do perfil. Instale firmware por fluxo oficial do RPCS3 e confira os logs/estado. Encontrar o arquivo não prova que a versão do binário inicializará o XMB; registre um boot real no host.

### PlayStation 2 — PCSX2 / BIOS Browser
O perfil procura BIOS `.bin` em `data/environments/pcsx2/bios/pcsx2/` e locais configurados do PCSX2 no `home/`. Confirme a seleção na interface do emulador. Um arquivo arbitrário com extensão/nome esperado não é necessariamente um dump válido.

### PlayStation 1 — DuckStation / BIOS shell
A rota é condicional à detecção de arquivo BIOS compatível e ao reconhecimento do argumento pelo build instalado. Teste visualmente no host; o lock de asset não certifica o dump da BIOS.

### PlayStation Portable — PPSSPP / VSH-XMB
A estratégia experimental procura firmware em `data/environments/ppsspp/bios/flash0/`, incluindo `vsh/module/vshmain.prx` e `kd/pspbtcnf.bin`. O caminho usa `--vsh` em versões compatíveis, mas o boot VSH do upstream é exploratório e não deve ser descrito como estável/garantido. Referências: [CLI oficial do PPSSPP](https://www.ppsspp.org/docs/reference/command-line/) e [investigação upstream de VSH](https://github.com/hrydgard/ppsspp/blob/master/docs/VSHBootInvestigation.md).

### Xbox original — xemu
Configuração em `data/environments/xemu/home/.config/xemu/xemu.toml`. O arquivo deve apontar para MCPX boot ROM, BIOS/Flash ROM e HDD dentro dos mounts permitidos. A presença do TOML/HDD não prova dashboard Microsoft original. O comando de atestação abaixo exige uma confirmação explícita e vincula a declaração ao hash do HDD:

```bash
python3 scripts/attest-xemu-dashboard.py --hdd data/environments/xemu/saves/SEU-HDD-DUMP --confirm-original-microsoft-dashboard
```

Troque o caminho pelo arquivo real que também corresponde ao `hdd_path` configurado. Não use a atestação para contornar dúvida: **ela registra uma declaração do operador, não inspeciona nem autentica criptograficamente o dashboard dentro do HDD.** Consulte [documentação oficial de arquivos exigidos do xemu](https://xemu.app/docs/required-files/).

### Nintendo Wii — Dolphin
O perfil verifica o Wii System Menu no NAND persistente do Dolphin, normalmente sob `data/environments/dolphin/home/.local/share/dolphin-emu/Wii/`. Configure o NAND e System Menu usando fluxo autorizado e teste o boot. Diretório encontrado não significa que os menus e jogos são válidos.

### Nintendo Wii U — Cemu
O estado MLC separado é esperado em `data/environments/cemu/home/.local/share/Cemu/mlc01/`. A rota procura `men.rpx` em caminhos de região conhecidos. Requer conteúdo de sistema configurado; uma pasta MLC vazia não serve.

### Azahar e melonDS
Os fluxos de firmware/menu são manuais ou condicionais. Abra e configure o emulador diretamente se a integração não declarar uma estratégia de boot automática. Não assuma que a interface do próprio emulador é o menu de console original.

### Nintendo Switch, PS4, PS5, Xbox 360/One/Series e PS Vita
O perfil não é uma promessa de boot integral do sistema original. Alguns focam jogos compatíveis e a maturidade depende do upstream; Xbox One/Series ficam bloqueados sem runner completo; PS5 é experimental. Vita3K tem sua própria UI, não um LiveArea original. Não substitua um caminho ausente por um dashboard falso em HTML.

### Sistemas clássicos (GB/GBA, NES, SNES, N64 e similares)
Esses sistemas usam sequências de inicialização específicas e não possuem necessariamente um dashboard moderno análogo ao XMB/Home Menu. A ausência de “dashboard de console” não significa ausência de emulação de jogos.

## 🔍 Como conferir o estado

Na seção **Sistemas originais**, examine pré-requisitos, estratégia e mensagem do perfil. Depois:
1. verifique o relatório de instalação e a versão do binário;
2. confira o log do agente;
3. tente o boot no host com GUI/renderer configurados;
4. registre o resultado e a combinação de firmware/binário;
5. mantenha indisponível o que não foi comprovado.

## 📚 Referências de linha de comando upstream

Esses links documentam sintaxe/opções; não são provas de que a rota específica funcione em cada build:

- [PCSX2 CLI](https://pcsx2.net/docs/advanced/cli/)
- [Dolphin](https://github.com/dolphin-emu/dolphin/blob/master/Readme.md?plain=1)
- [Cemu LaunchSettings](https://github.com/cemu-project/Cemu/blob/main/src/config/LaunchSettings.cpp)
- [xemu CLI](https://xemu.app/docs/cli/)
- [RPCS3 BootVSH implementation](https://github.com/RPCS3/rpcs3/blob/master/rpcs3/rpcs3qt/main_window.cpp)
- [PPSSPP CLI](https://www.ppsspp.org/docs/reference/command-line/)

EmuStack não fornece BIOS, firmware, chaves, NAND, MLC, HDDs nem imagens proprietárias. Os arquivos usados nos testes ficam no seu host e não devem ser enviados em issues/PRs.
