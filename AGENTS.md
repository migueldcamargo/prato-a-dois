# Instruções para agentes (Claude, Codex, etc.)

App: **Prato a Dois**, PWA em português do Brasil para casais registrarem pratos. Visão geral e tabela de máquinas de estado no `README.md`. Leia antes de mudar qualquer coisa.

## Regras do projeto

- **Sem build.** HTML/CSS/JS puros. Não introduza bundler, framework ou dependência nova no app sem pedido explícito.
- **Interface 100% pt-BR**, mobile-first (360–430 px), áreas de toque ≥ 44 px. Todo texto vindo do banco passa por `esc()` antes de ir para o HTML.
- **Lógica pura vai em `logica.js`** (sem DOM, rede ou `Date.now()`; receba `hoje`/`rng` por parâmetro). Funções devolvem estado novo, nunca alteram o recebido.
- **Estados são explícitos.** Não crie booleanos soltos para fases de tela/carga. Use as máquinas existentes (`S.screen`, `S.tab`, `S.carga` via `setCarga`, `S.sync` via `setSync`, `FALHAS`, `C.fase`) ou crie uma nova no mesmo padrão e registre no `README.md`.
- **Papéis:** `ACOES_PAPEL` (logica.js) e a função `definir_papel` (supabase.sql) aceitam exatamente as mesmas transições. Mude os dois juntos.
- **Banco:** `supabase.sql` precisa continuar idempotente (rodar duas vezes não pode falhar nem apagar dados). Toda mudança de esquema sobe `versao_banco()`. Se o app passar a depender dela, suba `BANCO_VERSAO_MIN` e garanta que o app continua funcionando (degradado) no banco antigo. Agentes não têm acesso ao Supabase: diga ao usuário para rodar o SQL no SQL Editor.
- **Cache:** mudou arquivo servido? Suba `APP_VERSAO` em `index.html` e `CACHE` em `sw.js`. Arquivo novo servido? Inclua em `ARQUIVOS` no `sw.js`.
- **Segredos:** `config.js` só pode ter a Publishable key (`sb_publishable_…`) ou a anon key. Nunca secret/service_role.

## Como testar (obrigatório antes de subir para a main)

```bash
node dev/test_logica.mjs        # deve terminar com "11 testes passaram" (ou mais)
dev/reset_db.sh && (python3 dev/fake_supabase.py &) && python3 dev/e2e.py   # deve terminar com "N/N verificações passaram"
```

O e2e precisa de Postgres local (porta via `PGPORT`, padrão 54329, socket em `/tmp`) e de `cd dev && npm install`. Sempre recrie o banco antes de rodar o e2e: ele assume banco vazio.

## Ganchos úteis

- Botões globais: `data-act="..."` (switch em "Ações globais" no `index.html`). Botões de painel: `data-x="..."`.
- `window.__prato` expõe `S` (estado), `T` (tabelas espelhadas do Supabase), `Logica` e `versao` para depuração e testes.
- Chaves do aparelho: `pd:nome`, `pd:meus`, `pd:ultimo`, `pd:filtros`, `pd:tutorial`, `pd-auth`.

## Publicação

Push na `main` → GitHub Pages publica em 1–2 min (https://migueldcamargo.github.io/prato-a-dois/). Commits em português, dizendo o que mudou para o usuário.
