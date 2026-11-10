# Prato a Dois

O cardápio do casal: os pratos que vocês já fizeram em casa ou pediram, com notas, histórico e dois jogos para decidir o que comer. Funciona como app instalado no celular (PWA), sem login.

- **App:** https://migueldcamargo.github.io/prato-a-dois/
- **Implantar do zero:** [`docs/guia-de-implantacao.html`](docs/guia-de-implantacao.html) (Supabase + GitHub Pages, passo a passo)
- **Atualizar o banco:** rode o [`supabase.sql`](supabase.sql) inteiro no SQL Editor do Supabase. Ele é idempotente e não apaga dados. O app avisa em Configurações quando o banco está desatualizado.

## Arquivos

| Arquivo | O que é |
|---|---|
| `index.html` | Interface inteira (HTML, CSS e JS). Telas, rede, eventos. |
| `logica.js` | Regras e máquinas de estado **puras** (sem tela, rede ou relógio). Testável no Node. |
| `config.js` | Project URL e Publishable key do Supabase. Só chave pública aqui. |
| `supabase.sql` | Banco completo: tabelas, regras de acesso (RLS), funções, Realtime e versão. |
| `sw.js`, `manifest.webmanifest`, `*.png` | Instalação na tela de início e funcionamento offline básico. |
| `docs/` | Guia de implantação (gerado por `dev/gerar_guia.py`). |
| `dev/` | Testes e servidor local que imita o Supabase. Não é usado pelo app. |

## Como funciona

- **Hospedagem:** site estático no GitHub Pages; não há build. Biblioteca `@supabase/supabase-js` 2.118.0 vem do jsDelivr.
- **Identidade:** login anônimo do Supabase, um por aparelho. O nome fica no aparelho. Sair apaga a sessão (não há como voltar à mesma identidade).
- **Dados:** tabelas `cardapios`, `membros`, `categorias`, `pratos`, `fotos`, `notas`, `feitos`. Cada gravação mexe em uma linha só, então duas pessoas não sobrescrevem uma à outra.
- **Acesso:** só membro lê; só dono e editor alteram; cada um grava só a própria nota. Mudanças de papel passam pela função `definir_papel`, que aceita só as transições da tabela abaixo.
- **Ao vivo:** Supabase Realtime; se cair, o app relê a cada 20 s e também ao trocar de aba ou voltar para o app.

## Máquinas de estado

Todas explícitas: cada uma tem um nome, uma lista fechada de estados e funções de transição.

| Máquina | Onde | Estados | Transições |
|---|---|---|---|
| Tela | `S.screen` em `index.html` | `splash` → `fatal` \| `onboard` → `home` ⇄ `card` | `boot`, `falhar(codigo)`, `goHome`, `openCardapio` |
| Aba do cardápio | `S.tab` / `ABAS` | `cardapio`, `decidir`, `historico`, `config` | clique em `data-act="tab"` |
| Carga do cardápio | `S.carga` | `carregando` → `pronto` \| `lento` \| `erro` (sumiu → volta pra home) | `setCarga`, `loadAll`, `cardapioSumiu` |
| Sincronização | `S.sync` | `desligado` → `conectando` → `ao-vivo` \| `periodico` | `setSync`, `subscribe`, `startPoll`, `unsubscribe` |
| Falhas de início | `FALHAS` | `semConfig`, `semBiblioteca`, `configInvalida`, `semAnonimo`, `chaveInvalida`, `urlInvalida`, `semLogin` | `falhar(codigo)` |
| Instalação | `estadoInstalacao()` | `instalado`, `ios-safari`, `ios-outro`, `android`, `computador` | derivada do aparelho |
| Atributo do prato | `logica.js` + banco | `null` (sem resposta), opção A, opção B, `ambos` (os dois) | formulário e classificação rápida |
| Duelo de categorias | `logica.js` | `duelando` → `fim` | `dueloEscolher(campeao \| desafiante \| os-dois)`, `dueloDesfazer` |
| Isso ou aquilo | `logica.js` | `jogando` → `ranking` → (`jogando` de novo) | `iouEscolher(cima \| baixo \| os-dois \| fica \| descarta)`, `iouDesfazer`, `iouNovaRodada(ranking \| todos)` |
| Papel no cardápio | `ACOES_PAPEL` em `logica.js` = `definir_papel` no SQL | `visitante`, `leitor`, `pendente`, `editor`, `dono` | aprovar, recusar, tornar dono, tirar edição, remover; pedir edição (a própria pessoa) |
| Classificação rápida | `C.fase` em `openClassify` | `pergunta` → `classificando` → `fim` | arrastar, botões, desfazer |

Transições de papel aceitas (as mesmas no app e no banco):

```
pendente → editor   (aprovar)        editor → dono    (tornar dono)
pendente → leitor   (recusar)        editor → leitor  (tirar edição)
leitor   → sai      (remover)        leitor → pendente (a própria pessoa pede)
Dono nunca é rebaixado nem removido por outra pessoa.
```

## Desenvolvimento

Testes da lógica (só Node, sem dependências):

```bash
node dev/test_logica.mjs
```

Teste ponta a ponta (dois navegadores contra um Postgres local com as regras de acesso de verdade):

```bash
pip install playwright "psycopg[binary]" pillow
(cd dev && npm install)                 # baixa o supabase-js usado nos testes
dev/reset_db.sh                         # precisa de um Postgres local; ajuste PGHOST/PGPORT
python3 dev/fake_supabase.py &          # imita auth anônima + API do Supabase na porta 8787
python3 dev/e2e.py                      # 55 verificações; telas em dev/saida/
```

Regenerar o guia depois de mudar o `supabase.sql`: `python3 dev/gerar_guia.py`.

## Checklist ao mudar algo

1. Regra ou jogo novo? Coloque em `logica.js` como função pura e teste em `dev/test_logica.mjs`.
2. Mudou o banco? Mantenha o `supabase.sql` idempotente, suba `versao_banco()` e, se o app depender, `BANCO_VERSAO_MIN` no `index.html`. Regenere o guia. Avise quem cuida do Supabase para rodar o SQL.
3. Mudou papéis? Altere `ACOES_PAPEL` e `definir_papel` juntos.
4. Mudou arquivos do app? Suba `APP_VERSAO` (index.html) e o `CACHE` do `sw.js`.
5. Rode os dois testes antes de subir para a `main` (o GitHub Pages publica sozinho).
