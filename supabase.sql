-- =====================================================================
--  PRATO A DOIS · banco de dados para o Supabase · VERSÃO 2
--  Como usar: no Supabase, abra "SQL Editor", cole TUDO e clique em "Run".
--  Pode rodar de novo sem medo: o script não apaga dados existentes.
--  Para atualizar de uma versão anterior, é só rodar este arquivo inteiro de novo.
--
--  Mudou algo aqui? Suba o número em versao_banco() (seção 6) e, se o app
--  depender da mudança, o BANCO_VERSAO_MIN em index.html.
--  Histórico:  v1 · estrutura inicial
--              v2 · opção "ambos" (os dois) nos atributos; transições de papel explícitas
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Tabelas
-- ---------------------------------------------------------------------

-- Um cardápio por casal. O código tem 5 caracteres, sem 0, O, 1, I e L.
create table if not exists public.cardapios (
  codigo     text primary key check (codigo ~ '^[A-HJKMNP-Z2-9]{5}$'),
  nome       text not null check (char_length(nome) between 1 and 40),
  dono       uuid not null,
  criado_em  timestamptz not null default now()
);

-- Quem participa de cada cardápio e com qual papel.
create table if not exists public.membros (
  cardapio   text not null references public.cardapios(codigo) on delete cascade,
  user_id    uuid not null,
  nome       text not null default 'Alguém' check (char_length(nome) between 1 and 30),
  papel      text not null default 'leitor' check (papel in ('dono', 'editor', 'leitor', 'pendente')),
  criado_em  timestamptz not null default now(),
  primary key (cardapio, user_id)
);
create index if not exists membros_user_idx on public.membros (user_id);

-- Categorias de cada cardápio (as 14 iniciais são criadas junto com o cardápio).
create table if not exists public.categorias (
  id         uuid primary key default gen_random_uuid(),
  cardapio   text not null references public.cardapios(codigo) on delete cascade,
  nome       text not null check (char_length(nome) between 1 and 24),
  icone      text not null default '🍴',
  ordem      int  not null default 0,
  criado_em  timestamptz not null default now()
);
create unique index if not exists categorias_nome_unico on public.categorias (cardapio, lower(nome));

-- Pratos. Os 4 atributos do quiz são opcionais (null = sem resposta; 'ambos' = os dois).
create table if not exists public.pratos (
  id            uuid primary key default gen_random_uuid(),
  cardapio      text not null references public.cardapios(codigo) on delete cascade,
  nome          text not null check (char_length(nome) between 1 and 60),
  origem        text not null check (origem in ('casa', 'restaurante')),
  restaurante   text not null default '' check (char_length(restaurante) <= 50),
  categorias    uuid[] not null default '{}',
  tempo         text check (tempo   in ('rapido', 'elaborado', 'ambos')),
  peso          text check (peso    in ('leve', 'encorpado', 'ambos')),
  sabor         text check (sabor   in ('salgado', 'doce', 'ambos')),
  ocasiao       text check (ocasiao in ('diadia', 'especial', 'ambos')),
  criado_por    uuid not null default auth.uid(),
  criado_em     timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),
  unique (id, cardapio)
);
create index if not exists pratos_cardapio_idx on public.pratos (cardapio);

-- v2: bancos criados na v1 ganham a opção 'ambos' nos 4 atributos (refaz as regras de valor).
alter table public.pratos drop constraint if exists pratos_tempo_check;
alter table public.pratos add  constraint pratos_tempo_check   check (tempo   in ('rapido', 'elaborado', 'ambos'));
alter table public.pratos drop constraint if exists pratos_peso_check;
alter table public.pratos add  constraint pratos_peso_check    check (peso    in ('leve', 'encorpado', 'ambos'));
alter table public.pratos drop constraint if exists pratos_sabor_check;
alter table public.pratos add  constraint pratos_sabor_check   check (sabor   in ('salgado', 'doce', 'ambos'));
alter table public.pratos drop constraint if exists pratos_ocasiao_check;
alter table public.pratos add  constraint pratos_ocasiao_check check (ocasiao in ('diadia', 'especial', 'ambos'));

-- Fotos ficam numa tabela à parte (texto base64, máx. ~300 KB) para a lista de pratos carregar rápido.
create table if not exists public.fotos (
  prato_id      uuid primary key,
  cardapio      text not null,
  data          text not null check (data like 'data:image/%' and char_length(data) < 400000),
  atualizado_em timestamptz not null default now(),
  foreign key (prato_id, cardapio) references public.pratos (id, cardapio) on delete cascade
);
create index if not exists fotos_cardapio_idx on public.fotos (cardapio);

-- Nota de cada pessoa para cada prato (1 a 5).
create table if not exists public.notas (
  prato_id      uuid not null,
  cardapio      text not null,
  user_id       uuid not null default auth.uid(),
  nota          int  not null check (nota between 1 and 5),
  atualizado_em timestamptz not null default now(),
  primary key (prato_id, user_id),
  foreign key (prato_id, cardapio) references public.pratos (id, cardapio) on delete cascade
);
create index if not exists notas_cardapio_idx on public.notas (cardapio);

-- Cada "Fizemos hoje" / "Pedimos hoje".
create table if not exists public.feitos (
  id         uuid primary key default gen_random_uuid(),
  prato_id   uuid not null,
  cardapio   text not null,
  data       date not null default current_date,
  por        uuid not null default auth.uid(),
  criado_em  timestamptz not null default now(),
  foreign key (prato_id, cardapio) references public.pratos (id, cardapio) on delete cascade
);
create index if not exists feitos_cardapio_idx on public.feitos (cardapio);

-- ---------------------------------------------------------------------
-- 2. Funções de apoio para as regras de acesso
-- ---------------------------------------------------------------------

create or replace function public.e_membro(p_cardapio text) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.membros where cardapio = p_cardapio and user_id = auth.uid());
$$;

create or replace function public.pode_editar(p_cardapio text) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.membros
                 where cardapio = p_cardapio and user_id = auth.uid() and papel in ('dono', 'editor'));
$$;

create or replace function public.e_dono(p_cardapio text) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.membros
                 where cardapio = p_cardapio and user_id = auth.uid() and papel = 'dono');
$$;

-- ---------------------------------------------------------------------
-- 3. Regras de acesso (Row Level Security)
--    Só quem é membro enxerga um cardápio; só dono e editor alteram.
-- ---------------------------------------------------------------------

alter table public.cardapios  enable row level security;
alter table public.membros    enable row level security;
alter table public.categorias enable row level security;
alter table public.pratos     enable row level security;
alter table public.fotos      enable row level security;
alter table public.notas      enable row level security;
alter table public.feitos     enable row level security;

drop policy if exists cardapios_ler       on public.cardapios;
drop policy if exists cardapios_renomear  on public.cardapios;
create policy cardapios_ler      on public.cardapios for select to authenticated using (public.e_membro(codigo));
create policy cardapios_renomear on public.cardapios for update to authenticated
  using (public.e_dono(codigo)) with check (public.e_dono(codigo));

drop policy if exists membros_ler on public.membros;
create policy membros_ler on public.membros for select to authenticated using (public.e_membro(cardapio));

drop policy if exists categorias_ler     on public.categorias;
drop policy if exists categorias_criar   on public.categorias;
drop policy if exists categorias_alterar on public.categorias;
drop policy if exists categorias_apagar  on public.categorias;
create policy categorias_ler     on public.categorias for select to authenticated using (public.e_membro(cardapio));
create policy categorias_criar   on public.categorias for insert to authenticated with check (public.pode_editar(cardapio));
create policy categorias_alterar on public.categorias for update to authenticated
  using (public.pode_editar(cardapio)) with check (public.pode_editar(cardapio));
create policy categorias_apagar  on public.categorias for delete to authenticated using (public.pode_editar(cardapio));

drop policy if exists pratos_ler     on public.pratos;
drop policy if exists pratos_criar   on public.pratos;
drop policy if exists pratos_alterar on public.pratos;
drop policy if exists pratos_apagar  on public.pratos;
create policy pratos_ler     on public.pratos for select to authenticated using (public.e_membro(cardapio));
create policy pratos_criar   on public.pratos for insert to authenticated
  with check (public.pode_editar(cardapio) and criado_por = auth.uid());
create policy pratos_alterar on public.pratos for update to authenticated
  using (public.pode_editar(cardapio)) with check (public.pode_editar(cardapio));
create policy pratos_apagar  on public.pratos for delete to authenticated using (public.pode_editar(cardapio));

drop policy if exists fotos_ler     on public.fotos;
drop policy if exists fotos_criar   on public.fotos;
drop policy if exists fotos_alterar on public.fotos;
drop policy if exists fotos_apagar  on public.fotos;
create policy fotos_ler     on public.fotos for select to authenticated using (public.e_membro(cardapio));
create policy fotos_criar   on public.fotos for insert to authenticated with check (public.pode_editar(cardapio));
create policy fotos_alterar on public.fotos for update to authenticated
  using (public.pode_editar(cardapio)) with check (public.pode_editar(cardapio));
create policy fotos_apagar  on public.fotos for delete to authenticated using (public.pode_editar(cardapio));

drop policy if exists notas_ler     on public.notas;
drop policy if exists notas_criar   on public.notas;
drop policy if exists notas_alterar on public.notas;
drop policy if exists notas_apagar  on public.notas;
create policy notas_ler     on public.notas for select to authenticated using (public.e_membro(cardapio));
create policy notas_criar   on public.notas for insert to authenticated
  with check (user_id = auth.uid() and public.pode_editar(cardapio));
create policy notas_alterar on public.notas for update to authenticated
  using (user_id = auth.uid() and public.pode_editar(cardapio))
  with check (user_id = auth.uid() and public.pode_editar(cardapio));
create policy notas_apagar  on public.notas for delete to authenticated
  using (user_id = auth.uid() and public.pode_editar(cardapio));

drop policy if exists feitos_ler    on public.feitos;
drop policy if exists feitos_criar  on public.feitos;
drop policy if exists feitos_apagar on public.feitos;
create policy feitos_ler    on public.feitos for select to authenticated using (public.e_membro(cardapio));
create policy feitos_criar  on public.feitos for insert to authenticated
  with check (por = auth.uid() and public.pode_editar(cardapio));
create policy feitos_apagar on public.feitos for delete to authenticated using (public.pode_editar(cardapio));

-- Permissões por coluna: ninguém troca o dono, o código ou o cardápio de um prato pela API.
revoke all on public.cardapios, public.membros, public.categorias, public.pratos,
              public.fotos, public.notas, public.feitos from anon;
revoke insert, update, delete on public.cardapios from authenticated;
grant  select on public.cardapios to authenticated;
grant  update (nome) on public.cardapios to authenticated;
revoke insert, update, delete on public.membros from authenticated;
grant  select on public.membros to authenticated;
grant  select, insert, delete on public.categorias, public.pratos to authenticated;
revoke update on public.categorias, public.pratos from authenticated;
grant  update (nome, icone, ordem) on public.categorias to authenticated;
grant  update (nome, origem, restaurante, categorias, tempo, peso, sabor, ocasiao, atualizado_em) on public.pratos to authenticated;
grant  select, insert, update, delete on public.fotos, public.notas to authenticated;
revoke update on public.feitos from authenticated;
grant  select, insert, delete on public.feitos to authenticated;

-- ---------------------------------------------------------------------
-- 4. Ações que precisam de regra especial (chamadas pelo app)
-- ---------------------------------------------------------------------

-- Cria um cardápio com código único, a pessoa como dona e as categorias iniciais.
create or replace function public.criar_cardapio(p_nome text, p_meu_nome text) returns text
language plpgsql security definer set search_path = public as $$
declare
  v_codigo    text;
  v_chars     constant text := 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
  v_tentativa int := 0;
begin
  if auth.uid() is null then raise exception 'Sessão não encontrada.'; end if;
  loop
    v_tentativa := v_tentativa + 1;
    v_codigo := '';
    for i in 1..5 loop
      v_codigo := v_codigo || substr(v_chars, 1 + floor(random() * length(v_chars))::int, 1);
    end loop;
    begin
      insert into cardapios (codigo, nome, dono)
      values (v_codigo, left(coalesce(nullif(btrim(p_nome), ''), 'Nosso cardápio'), 40), auth.uid());
      exit;
    exception when unique_violation then
      if v_tentativa > 25 then raise; end if;
    end;
  end loop;

  insert into membros (cardapio, user_id, nome, papel)
  values (v_codigo, auth.uid(), left(coalesce(nullif(btrim(p_meu_nome), ''), 'Dono'), 30), 'dono');

  insert into categorias (cardapio, nome, icone, ordem)
  select v_codigo, c.nome, c.icone, c.ordem
  from (values ('Hambúrguer', '🍔', 1), ('Pizza', '🍕', 2), ('Massas', '🍝', 3), ('Risoto', '🍚', 4),
               ('Asiática', '🥢', 5), ('Japonesa', '🍣', 6), ('Churrasco', '🔥', 7), ('Carnes', '🥩', 8),
               ('Saladas', '🥗', 9), ('Wraps', '🌯', 10), ('Sopas', '🍲', 11), ('Lanches', '🥪', 12),
               ('Air fryer', '🍟', 13), ('Sobremesas', '🍰', 14)) as c (nome, icone, ordem);
  return v_codigo;
end $$;

-- Entra num cardápio pelo código (como leitor). Devolve null se o código não existe.
create or replace function public.entrar_cardapio(p_codigo text, p_meu_nome text) returns json
language plpgsql security definer set search_path = public as $$
declare
  v_card  cardapios;
  v_papel text;
begin
  if auth.uid() is null then raise exception 'Sessão não encontrada.'; end if;
  select * into v_card from cardapios where codigo = upper(btrim(p_codigo));
  if not found then return null; end if;
  insert into membros (cardapio, user_id, nome, papel)
  values (v_card.codigo, auth.uid(), left(coalesce(nullif(btrim(p_meu_nome), ''), 'Alguém'), 30), 'leitor')
  on conflict (cardapio, user_id) do nothing;
  select papel into v_papel from membros where cardapio = v_card.codigo and user_id = auth.uid();
  return json_build_object('codigo', v_card.codigo, 'nome', v_card.nome, 'papel', v_papel);
end $$;

-- Leitor pede para poder editar.
create or replace function public.pedir_edicao(p_codigo text) returns boolean
language plpgsql security definer set search_path = public as $$
begin
  update membros set papel = 'pendente'
  where cardapio = p_codigo and user_id = auth.uid() and papel = 'leitor';
  return found;
end $$;

-- Dono muda o papel de outra pessoa. Só valem estas transições (iguais a ACOES_PAPEL em logica.js):
--   aprovar      pendente → editor        recusar  pendente → leitor
--   tornar dono  editor   → dono          tirar edição  editor → leitor
--   remover      leitor   → (sai do cardápio)
-- Dono nunca é rebaixado nem removido por outra pessoa.
create or replace function public.definir_papel(p_codigo text, p_user uuid, p_papel text) returns boolean
language plpgsql security definer set search_path = public as $$
declare v_atual text;
begin
  if not public.e_dono(p_codigo) then raise exception 'Só o dono pode fazer isso.'; end if;
  if p_user = auth.uid() then raise exception 'Você não pode mudar o seu próprio papel.'; end if;
  select papel into v_atual from membros where cardapio = p_codigo and user_id = p_user for update;
  if not found then raise exception 'Essa pessoa não está neste cardápio.'; end if;
  if (v_atual, p_papel) not in (('pendente', 'editor'), ('pendente', 'leitor'),
                                ('editor', 'dono'), ('editor', 'leitor'),
                                ('leitor', 'remover')) then
    raise exception 'Mudança de papel não permitida: % para %.', v_atual, p_papel;
  end if;
  if p_papel = 'remover' then
    delete from membros where cardapio = p_codigo and user_id = p_user;
  else
    update membros set papel = p_papel where cardapio = p_codigo and user_id = p_user;
  end if;
  return true;
end $$;

-- Atualiza o nome da pessoa em todos os cardápios dela.
create or replace function public.renomear_me(p_nome text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if nullif(btrim(p_nome), '') is null then return; end if;
  update membros set nome = left(btrim(p_nome), 30) where user_id = auth.uid();
end $$;

revoke execute on function public.criar_cardapio(text, text)          from public, anon;
revoke execute on function public.entrar_cardapio(text, text)         from public, anon;
revoke execute on function public.pedir_edicao(text)                  from public, anon;
revoke execute on function public.definir_papel(text, uuid, text)     from public, anon;
revoke execute on function public.renomear_me(text)                   from public, anon;
revoke execute on function public.e_membro(text)                      from public, anon;
revoke execute on function public.pode_editar(text)                   from public, anon;
revoke execute on function public.e_dono(text)                        from public, anon;
grant  execute on function public.criar_cardapio(text, text)          to authenticated;
grant  execute on function public.entrar_cardapio(text, text)         to authenticated;
grant  execute on function public.pedir_edicao(text)                  to authenticated;
grant  execute on function public.definir_papel(text, uuid, text)     to authenticated;
grant  execute on function public.renomear_me(text)                   to authenticated;
grant  execute on function public.e_membro(text)                      to authenticated;
grant  execute on function public.pode_editar(text)                   to authenticated;
grant  execute on function public.e_dono(text)                        to authenticated;

-- ---------------------------------------------------------------------
-- 5. Atualização ao vivo (Realtime): o que um faz aparece no celular do outro
-- ---------------------------------------------------------------------
do $$
declare t text;
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    foreach t in array array['cardapios', 'membros', 'categorias', 'pratos', 'fotos', 'notas', 'feitos'] loop
      begin
        execute format('alter publication supabase_realtime add table public.%I', t);
      exception when duplicate_object then null;
      end;
    end loop;
  end if;
end $$;

-- ---------------------------------------------------------------------
-- 6. Versão do banco: o app lê para saber o que este banco já suporta
-- ---------------------------------------------------------------------
create or replace function public.versao_banco() returns int
language sql immutable as $$ select 2 $$;
revoke execute on function public.versao_banco() from public, anon;
grant  execute on function public.versao_banco() to authenticated;

-- Pronto! Deve aparecer "Success. No rows returned".
