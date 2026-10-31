# 🛠️ Fase 1 — Gerenciador de emuladores por perfil

O EmuStack possui **duas vias complementares de instalação**, que não devem ser confundidas:

1. **Imagem Docker oficial:** \`release-lock.json\`, pacotes Debian e \`scripts/install-upstream.py\` mantêm os executáveis oficiais já instalados durante o build. Reconstruir a imagem continua sendo a forma de renovar esses assets.
2. **Gerenciador de host:** \`scripts/emulator-manager.py\` mantém binários adicionais *somente* em \`data/environments/<id>/emulators/\`, que é montado **somente leitura** no agente daquele console. Não monta o socket Docker no dashboard, não executa comandos arbitrários pela API e não mexe nos arquivos de jogos/saves.

## Estado de integração (não confundir com compatibilidade)

| Perfil | Situação de Fase 1 |
|---|---|
| PPSSPP, melonDS, bsnes | Receita de compilação Linux pinada, a partir do checkout de \`third_party\`, **não validada no host até executar o build**; importação revisada e rollback disponíveis |
| RPCS3, DuckStation, PCSX2, Vita3K, Xenia Canary, xemu, Eden, Cemu, Dolphin, Azahar, mGBA, Mupen64Plus e Mesen | Gerenciamento por release/apt existente, e importação manual auditável por perfil. Não recompilados automaticamente a partir dos submódulos |
| KytyPS5, shadPS4 | Fontes oficiais pinadas e auditáveis; **sem receita Linux genérica revisada nesta etapa**. KytyPS5 ainda tem o builder experimental independente do Dockerfile; não há garantia de instalação |
| Xbox One, Xbox Series | Sem runner suportado, instalação e execução **bloqueadas** |

Os 24 submódulos são **fontes**, não 24 pacotes prontos para rodar. Os três builds novos são *best effort* e não são parte automática do build da imagem: requerem dependências instaladas no host e podem falhar devido a mudanças upstream, submódulos internos ou bibliotecas.

## 1. Inspecionar antes de modificar

Sempre rode como usuário normal do Debian, na raiz do repositório, **sem sudo**:

\`\`\`bash
python3 scripts/upstream-manager.py audit --require-checkout
python3 scripts/emulator-manager.py status
python3 scripts/emulator-manager.py deps ppsspp
python3 scripts/emulator-manager.py deps melonds
python3 scripts/emulator-manager.py deps bsnes
\`\`\`

\`deps\` informa comandos de build que faltam, lista sugerida de pacotes e manual oficial. **Não instala pacotes automaticamente**. Verifique a versão e a disponibilidade no Debian antes de instalar dependências no host. Alguns projetos usam submódulos Git aninhados; revise as fontes e inicialize os submódulos internos necessários antes de compilar. O gerenciador recusa checkouts com commit errado, alterações não commitadas ou submódulos internos ausentes/divergentes.

## 2. Compilação explícita a partir de fonte fixada

\`\`\`bash
# Compilar um perfil, apenas após revisar o projeto upstream e dependências:
python3 scripts/emulator-manager.py build ppsspp --jobs 2 --yes-run-upstream-code
python3 scripts/emulator-manager.py build melonds --jobs 2 --yes-run-upstream-code
python3 scripts/emulator-manager.py build bsnes --jobs 2 --yes-run-upstream-code
\`\`\`

Esses comandos **executam o sistema de build de terceiros no host**, que não é uma sandbox. Se não confiar no código, compile numa VM/host descartável em vez de executar no computador principal. O gerenciador recusa execução como root, não faz downloads de firmware/jogos e executa comandos de build com lista fixa de argumentos (sem shell).

O código-fonte é copiado para \`data/emulator-manager/work/\` antes do build para não modificar os submódulos. Logs de erro ficam em \`data/emulator-manager/logs/\`. O binário só é promovido ao perfil se o arquivo esperado realmente existir e tiver conteúdo. **Isso não comprova que o programa abra no desktop ou tenha todos os recursos auxiliares**: PPSSPP e bsnes podem exigir assets/recursos adicionais para funcionar. Teste o aplicativo real após a compilação. Nenhuma compilação deve ser considerada verde apenas porque a rotina retornou.

## 3. Importar um binário revisado, com hash obrigatório

Para perfis com runner permitido, é possível usar um executável local obtido de fonte autorizada. Exemplo para arquivo que você *já possui*, cujo hash revisou independentemente:

\`\`\`bash
sha256sum /caminho/para/PPSSPPSDL
python3 scripts/emulator-manager.py install-file ppsspp /caminho/para/PPSSPPSDL \
  --binary-name PPSSPPSDL --sha256 HASH_REAL_DE_64_CARACTERES
\`\`\`

O \`--binary-name\` é validado contra \`catalog.json\`; nomes arbitrários, perfil bloqueado e symlinks são rejeitados. O SHA-256 garante **igualdade com o hash fornecido**, não autenticidade do fornecedor. Não copie jogos/BIOS/firmware para \`emulators/\`. Arquivos que não sejam executáveis aprovados podem causar falhas, mesmo com hash válido. \`install-file\` não faz download, não abre o binário e não verifica a licença.

A importação usa staging no mesmo filesystem, verificação de cópia e troca por \`os.replace\`. Se existia um binário local no mesmo caminho, a versão antiga é preservada em \`data/emulator-manager/versions/<id>/\`. A imagem Docker não é alterada. O agente reconhece o binário da pasta privada na próxima consulta, mas **pare sessões em andamento antes de atualizar ou reverter**.

## 4. Atualização por versão e rollback

\`\`\`bash
# Consultar novas referências oficiais, sem trocar os commits:
python3 scripts/upstream-manager.py plan --id melonds

# Pin: somente após auditoria, em branch separada:
# python3 scripts/upstream-manager.py pin melonds SHA_COMPLETO_REVISADO
# git diff --cached --submodule=log
# git commit -m "chore: update reviewed melonDS source pin"

# Construir novamente a partir do novo pin:
python3 scripts/emulator-manager.py build melonds --jobs 2 --yes-run-upstream-code

# Ver histórico, reverter ou remover somente o binário gerenciado:
python3 scripts/emulator-manager.py history melonds
python3 scripts/emulator-manager.py rollback melonds
python3 scripts/emulator-manager.py uninstall melonds
\`\`\`

\`rollback\` recupera a última versão salva, inclusive após uma desinstalação controlada. Históricos são locais: commits Git, relatórios de build e executáveis não são a mesma coisa. O gerenciador não altera automaticamente o \`source-lock.json\` nem o \`release-lock.json\` e não faz atualização silenciosa. Para atualizar **assets da imagem Docker**, use o workflow de freeze de hashes e o rebuild revisado descrito em [Releases e atualizações](RELEASE_AND_UPDATES.md).

## 5. Estado e segurança

\`\`\`bash
python3 scripts/emulator-manager.py status ppsspp
python3 scripts/emulator-manager.py history ppsspp
./scripts/validate-project.sh
USE_NVIDIA=1 ./scripts/runtime-acceptance.sh
\`\`\`

- \`managed_hash_valid\` certifica integridade do binário local em relação à instalação registrada; **não** certifica funcionalidade. \`runtime_tested\` permanece \`false\` até testes reais de aplicativo.
- \`availability: not-checked-in-host-runtime\` indica que o gerenciador não se apresenta como um monitor de jogabilidade. Consulte também os agentes e o relatório de instalação do runtime.
- \`source_build: not-integrated\` não significa indisponibilidade do emulador; releases oficiais ou APT podem fornecer o binário sem build fonte.
- Metadados de versões ficam em \`data/emulator-manager/active/\`, backups em \`versions/\`; **não** são compartilhados com dashboard/containers. Apenas o executável autorizado do perfil fica disponível em seu mount.
- Nunca execute compilações como root nem monte a API/porta do dashboard na rede externa para automatizar instalações. O painel continua intencionalmente sem permissões de instalação de pacotes no host.
- O rollback preserva arquivos de binário; não restaura alterações de formato de saves/configs feitas por novas versões. Use o backup de dados por perfil antes de upgrades incompatíveis.
- A exclusão/rollback não termina processos já iniciados. Encerre a sessão do emulador antes de substituir um executável.

## 6. Critérios de aceite pendentes

- Executar cada receita de build num host Debian com suas dependências reais e confirmar saída dos binários.
- Validar a presença de recursos complementares (assets) usados por cada emulador.
- Abrir a interface gráfica de cada emulador e executar um teste mínimo de conteúdo homebrew autorizado.
- Registrar drivers, versão do binário, dependências, logs, áudio, controles, save/load e encerramento.
- Exercitar rollback com o aplicativo fechado e garantir que dados persistentes permanecem corretos.

**A Fase 1 não será declarada integralmente concluída até que os builds e testes de aplicação tenham evidência no host.**
