# Identidade visual — EmuStack Gaming Lab

> **EMUSTACK // GAMING LAB** · [Visão geral](../README.md) · [Instalação](INSTALLATION.md) · [Guia do usuário](USER_GUIDE.md) · [Matriz de emuladores](EMULATOR_MATRIX.md) · [Segurança](SECURITY.md)

A identidade do EmuStack mistura **laboratório técnico**, **arcade contemporâneo** e **preservação multi-era**. A intenção é lembrar videogames sem virar uma colagem de logos ou comprometer a leitura de documentação de engenharia.

## Direção de arte

- **Base:** ambiente escuro, profundo e legível; interfaces com hierarquia visual clara.
- **Acabamento:** grid sutil, linhas de circuito, contornos finos e brilho controlado — sem efeitos que prejudiquem a leitura.
- **Era:** uma mistura de UI moderna com pequenos acenos a CRT, pixels e hardware de várias gerações.
- **Ícones:** desenho vetorial original e genérico. Não copiar logotipos oficiais das fabricantes nem criar a impressão de afiliação.
- **Mensagem:** mostrar variedade de sistemas sem afirmar que todos os runners foram instalados ou que todos os jogos funcionam.

## Paleta

| Função | Cor | Uso |
|---|---|---|
| Fundo base | <code>#0B1018</code> | Fundo global da aplicação. |
| Painel | <code>#101824</code> | Cartões, blocos e zonas de conteúdo. |
| Texto principal | <code>#EAF1F6</code> | Títulos e texto de alta prioridade. |
| Texto secundário | <code>#8B9BAB</code> | Descrições e metadados. |
| Teal arcade | <code>#58DFD0</code> | Ação principal, foco, conectividade e estado positivo. |
| Azul-violeta | <code>#8FA6FF</code> | PlayStation e elementos experimentais. |
| Rosa neon | <code>#FF91C9</code> | Destaque de arte, sem sinalizar estado crítico. |
| Verde | <code>#9EE8B3</code> | Família Xbox e estados positivos. |
| Coral | <code>#FFAAA8</code> | Família Nintendo e marcadores de coleção. |
| Âmbar | <code>#FFC97A</code> | Avisos, pré-requisitos e estado condicional. |
| Vermelho suave | <code>#FF8D9A</code> | Erros ou perfis bloqueados, nunca como decoração recorrente. |

O acento de uma família é apenas uma ferramenta de navegação. **Cor não substitui texto de estado**: “experimental”, “não suportado”, “launcher encontrado” e “boot observado” precisam continuar escritos explicitamente.

## Elementos gráficos

Os assets vetoriais da documentação são:

- <code>assets/emustack-hero.svg</code> — banner principal do README.
- <code>assets/emustack-architecture.svg</code> — diagrama lógico dos ambientes e mounts.
- <code>web/favicon.svg</code> — ícone usado pela interface local.
- <code>web/emustack-hero.svg</code> e <code>web/emustack-architecture.svg</code> — cópias servidas pelo visualizador local de documentação; manter sincronizadas com as versões em <code>assets/</code>.

As artes são SVGs editáveis, não carregam imagens externas, fontes remotas ou rastreadores. A grade da página inicial é decorativa e deve permanecer sutil. As animações respeitam <code>prefers-reduced-motion</code>.

## Vocabulário visual e editorial

Preferir:

- “perfil catalogado” para um ID definido no projeto;
- “launcher encontrado” para um binário detectado;
- “runner executável” quando a verificação correspondente passou;
- “boot tentado”, “boot observado” e “smoke test” como evidências separadas;
- “condicional” ou “experimental” quando existem pré-requisitos ou incerteza real.

Evitar “todos os consoles funcionam”, “compatibilidade total”, “dashboard original pronto” ou “20 consoles totalmente emulados” sem testes que sustentem essas afirmações. O desenho deve reforçar a precisão técnica, não esconder limitações.

## Checklist de revisão visual

- [ ] O conteúdo mantém contraste legível em telas pequenas.
- [ ] Cor e ícone não são a única forma de comunicar status.
- [ ] Cards e títulos mantêm hierarquia sem virar uma parede de badges.
- [ ] Todos os assets são vetoriais locais e sem dependências remotas.
- [ ] README, favicon e painel parecem pertencer ao mesmo produto.
- [ ] Toda afirmação de compatibilidade tem evidência e escopo explícitos.
