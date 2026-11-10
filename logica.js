/* =====================================================================
 * PRATO A DOIS · logica.js
 * Regras e máquinas de estado PURAS do app: nada de tela, rede ou relógio.
 * Cada função recebe um estado e um evento e devolve um estado NOVO
 * (nunca altera o que recebeu). Assim dá para testar tudo no Node:
 *   node dev/test_logica.mjs
 * No navegador, tudo fica em window.Logica.
 *
 * Máquinas daqui:
 *   1. Atributos do prato (tempo, peso, sabor, ocasião) com a opção "os dois"
 *   2. Filtros do "O que vamos comer?"
 *   3. Duelo de categorias  ("Hambúrguer ou pizza?")
 *   4. Isso ou aquilo       (prato contra prato, com ranking e rodadas)
 *   5. Papéis no cardápio   (quem pode virar o quê)  ← espelhado no supabase.sql
 * ===================================================================== */
(function (raiz) {
  "use strict";

  /* ---------- 1. Atributos ----------
   * Valor de cada atributo no banco: null (sem resposta) | a[0] | b[0] | "ambos".
   * "ambos" serve para pratos no meio-termo: passam em qualquer filtro daquele atributo. */
  const AMBOS = "ambos";
  const ATRIBUTOS = [
    { key: "tempo",   q: "Rápido ou elaborado?",          a: ["rapido", "Rápido", "⚡"],       b: ["elaborado", "Elaborado", "👨‍🍳"],      ambos: [AMBOS, "Os dois", "Tempo médio"] },
    { key: "peso",    q: "Leve ou encorpado?",             a: ["leve", "Leve", "🥗"],           b: ["encorpado", "Encorpado", "🍖"],       ambos: [AMBOS, "Os dois", "Peso médio"] },
    { key: "sabor",   q: "Salgado ou doce?",               a: ["salgado", "Salgado", "🧂"],     b: ["doce", "Doce", "🍫"],                 ambos: [AMBOS, "Os dois", "Doce e salgado"] },
    { key: "ocasiao", q: "Dia a dia ou ocasião especial?", a: ["diadia", "Dia a dia", "🏠"],    b: ["especial", "Ocasião especial", "🥂"], ambos: [AMBOS, "Os dois", "Dia a dia e especial"] }
  ];
  const VALORES_VALIDOS = {};
  const ROTULO_VALOR = {};
  ATRIBUTOS.forEach(a => {
    VALORES_VALIDOS[a.key] = [a.a[0], a.b[0], AMBOS];
    ROTULO_VALOR[a.key + ":" + a.a[0]] = a.a[1];
    ROTULO_VALOR[a.key + ":" + a.b[0]] = a.b[1];
    ROTULO_VALOR[a.key + ":" + AMBOS] = a.ambos[2];
  });
  const temAtributo = p => ATRIBUTOS.some(a => p && p.quiz && p.quiz[a.key]);

  /* ---------- 2. Filtros ----------
   * filtros = { origem, tempo, peso, sabor, ocasiao }; null = "tanto faz".
   * combina(): "sim" (bate ou é "os dois") | "talvez" (prato sem resposta) | "nao" (contradiz). */
  const FILTROS_VAZIOS = Object.freeze({ origem: null, tempo: null, peso: null, sabor: null, ocasiao: null });
  function combina(valor, desejado) {
    if (!desejado) return "sim";
    if (!valor) return "talvez";
    return valor === desejado || valor === AMBOS ? "sim" : "nao";
  }
  const origemDe = p => (p && p.origem === "restaurante" ? "restaurante" : "casa");
  /* Devolve a pontuação do prato (maior = bate melhor) ou null se ele sai do páreo. */
  function pontuar(prato, filtros) {
    const f = filtros || FILTROS_VAZIOS;
    if (f.origem && origemDe(prato) !== f.origem) return null;
    let pontos = 0;
    for (const a of ATRIBUTOS) {
      const r = combina(prato.quiz && prato.quiz[a.key], f[a.key]);
      if (r === "nao") return null;
      if (f[a.key]) pontos += r === "sim" ? 2 : 1;
    }
    return pontos;
  }
  function filtrar(pratos, filtros) {
    const out = [];
    for (const p of pratos) { const pts = pontuar(p, filtros); if (pts != null) out.push({ prato: p, pontos: pts }); }
    return out;
  }
  const filtrosAtivos = f => Object.keys(FILTROS_VAZIOS).filter(k => f && f[k]).length;

  /* Ajudantes de nota e histórico (datas sempre "AAAA-MM-DD", hoje vem de fora). */
  function media(p) {
    const l = Object.values((p && p.notas) || {}).filter(v => typeof v === "number" && v >= 1 && v <= 5);
    return l.length ? l.reduce((a, b) => a + b, 0) / l.length : null;
  }
  function ultimaData(p) {
    let u = null;
    Object.values((p && p.feitos) || {}).forEach(f => { if (f && f.d && (!u || f.d > u)) u = f.d; });
    return u;
  }
  const diaNum = s => { const [y, m, d] = s.split("-").map(Number); return Math.round(Date.UTC(y, m - 1, d) / 86400000); };
  const diasDesde = (data, hoje) => (data ? diaNum(hoje) - diaNum(data) : Infinity);
  /* Ordem das sugestões: quem bate mais nos filtros, depois maior nota, depois quem faz mais tempo que não sai. */
  function ordenarSugestoes(itens, hoje) {
    const nome = x => String(x.prato.nome || "");
    return itens.slice().sort((x, y) =>
      (y.pontos - x.pontos) ||
      ((media(y.prato) ?? -1) - (media(x.prato) ?? -1)) ||
      (diasDesde(ultimaData(y.prato), hoje) - diasDesde(ultimaData(x.prato), hoje)) ||
      nome(x).localeCompare(nome(y), "pt-BR"));
  }

  /* ---------- 3. Duelo de categorias ----------
   * Estados: "duelando" → "fim".
   * O campeão começa com a 1ª categoria; cada desafiante entra na ordem do cardápio.
   * Eventos: "campeao" (fica o campeão) | "desafiante" (troca) | "os-dois" (campeão vira um grupo).
   * Desfazer volta exatamente ao estado anterior (o estado guarda o anterior). */
  function dueloIniciar(ids) {
    const lista = (ids || []).slice();
    const total = Math.max(0, lista.length - 1);
    if (lista.length <= 1) return { fase: "fim", campeao: lista, fila: [], eliminadas: [], passo: 0, total, anterior: null };
    return { fase: "duelando", campeao: [lista[0]], fila: lista.slice(1), eliminadas: [], passo: 0, total, anterior: null };
  }
  function dueloEscolher(s, escolha) {
    if (!s || s.fase !== "duelando") return s;
    const desafiante = s.fila[0], resto = s.fila.slice(1);
    let campeao = s.campeao, eliminadas = s.eliminadas;
    if (escolha === "campeao") eliminadas = eliminadas.concat([desafiante]);
    else if (escolha === "desafiante") { eliminadas = eliminadas.concat(campeao); campeao = [desafiante]; }
    else if (escolha === "os-dois") campeao = campeao.concat([desafiante]);
    else throw new Error("Escolha inválida no duelo: " + escolha);
    return { fase: resto.length ? "duelando" : "fim", campeao, fila: resto, eliminadas, passo: s.passo + 1, total: s.total, anterior: s };
  }
  const dueloDesfazer = s => (s && s.anterior) || s;

  /* ---------- 4. Isso ou aquilo ----------
   * Estados: "jogando" → "ranking"; do ranking, uma nova rodada volta a "jogando".
   * A rodada embaralha os pratos e forma pares (o último pode ficar sozinho).
   * Eventos no par: "cima" | "baixo" (o outro é descartado) | "os-dois" (os dois vão pro final).
   * Eventos no prato sozinho: "fica" (vai pro final) | "descarta".
   * Vitórias somam entre rodadas e ordenam o ranking. */
  function embaralhar(lista, rng) {
    const r = rng || Math.random, a = lista.slice();
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); const t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }
  function iouIniciar(ids, opts) {
    const o = opts || {};
    const ordem = embaralhar(ids || [], o.rng);
    const pares = [];
    for (let i = 0; i < ordem.length; i += 2) pares.push(ordem.slice(i, i + 2));
    return {
      fase: pares.length ? "jogando" : "ranking",
      rodada: o.rodada || 1,
      todos: (o.todos || ids || []).slice(),
      pares, i: 0, resultado: {},
      vitorias: Object.assign({}, o.vitorias || {}),
      anterior: null
    };
  }
  function iouEscolher(s, escolha) {
    if (!s || s.fase !== "jogando") return s;
    const par = s.pares[s.i];
    const resultado = Object.assign({}, s.resultado), vitorias = Object.assign({}, s.vitorias);
    const ganha = id => { resultado[id] = "venceu"; vitorias[id] = (vitorias[id] || 0) + 1; };
    if (par.length === 2) {
      const cima = par[0], baixo = par[1];
      if (escolha === "cima") { ganha(cima); resultado[baixo] = "descartado"; }
      else if (escolha === "baixo") { ganha(baixo); resultado[cima] = "descartado"; }
      else if (escolha === "os-dois") { resultado[cima] = "final"; resultado[baixo] = "final"; }
      else throw new Error("Escolha inválida para um par: " + escolha);
    } else {
      if (escolha === "fica") resultado[par[0]] = "final";
      else if (escolha === "descarta") resultado[par[0]] = "descartado";
      else throw new Error("Escolha inválida para um prato sozinho: " + escolha);
    }
    const i = s.i + 1;
    return Object.assign({}, s, { i, resultado, vitorias, fase: i >= s.pares.length ? "ranking" : "jogando", anterior: s });
  }
  const iouDesfazer = s => (s && s.anterior) || s;
  /* desempate(a, b): número para ordenar empates de vitórias (ex.: maior nota primeiro). */
  function iouRanking(s, desempate) {
    const ids = [].concat.apply([], s.pares);
    const cmp = (a, b) => ((s.vitorias[b] || 0) - (s.vitorias[a] || 0)) || (desempate ? desempate(a, b) : 0);
    const de = st => ids.filter(id => s.resultado[id] === st).sort(cmp);
    return { ganharam: de("venceu"), final: de("final"), descartados: de("descartado") };
  }
  const iouSobreviventes = (s, desempate) => { const r = iouRanking(s, desempate); return r.ganharam.concat(r.final); };
  /* quais: "ranking" (só quem sobrou, mantendo vitórias) | "todos" (recomeça do zero) */
  function iouNovaRodada(s, quais, opts) {
    const o = opts || {};
    if (quais === "todos") return iouIniciar(s.todos, { rng: o.rng, todos: s.todos });
    return iouIniciar(iouSobreviventes(s), { rng: o.rng, todos: s.todos, vitorias: s.vitorias, rodada: s.rodada + 1 });
  }

  /* ---------- 5. Papéis ----------
   * visitante → (entrar com código) → leitor → (pedir) → pendente → (aprovar) → editor → (tornar dono) → dono
   * O dono age sobre os outros só por estas transições. O banco (definir_papel no supabase.sql)
   * aceita exatamente os mesmos pares (de → para). Mudou aqui? Mude lá e suba a versão do banco. */
  const PAPEIS = ["visitante", "leitor", "pendente", "editor", "dono"];
  const ROTULO_PAPEL = { dono: "Dono", editor: "Editor", leitor: "Leitor", pendente: "Aguardando aprovação", visitante: "Leitor" };
  const ACOES_PAPEL = {
    aprovar:      { de: "pendente", para: "editor",  rotulo: "Aprovar" },
    recusar:      { de: "pendente", para: "leitor",  rotulo: "Recusar" },
    tornar_dono:  { de: "editor",   para: "dono",    rotulo: "Tornar dono" },
    tirar_edicao: { de: "editor",   para: "leitor",  rotulo: "Tirar edição" },
    remover:      { de: "leitor",   para: "remover", rotulo: "Remover" }
  };
  const podeEditar = papel => papel === "dono" || papel === "editor";
  const ehDono = papel => papel === "dono";
  /* Ações que um dono pode fazer sobre alguém com esse papel (nunca sobre si mesmo). */
  function acoesSobre(meuPapel, papelAlvo, ehEuMesmo) {
    if (!ehDono(meuPapel) || ehEuMesmo) return [];
    return Object.keys(ACOES_PAPEL).filter(k => ACOES_PAPEL[k].de === papelAlvo);
  }
  const transicaoPermitida = (de, para) => Object.values(ACOES_PAPEL).some(a => a.de === de && a.para === para);

  const Logica = {
    AMBOS, ATRIBUTOS, VALORES_VALIDOS, ROTULO_VALOR, temAtributo,
    FILTROS_VAZIOS, combina, origemDe, pontuar, filtrar, filtrosAtivos,
    media, ultimaData, diasDesde, ordenarSugestoes,
    dueloIniciar, dueloEscolher, dueloDesfazer,
    embaralhar, iouIniciar, iouEscolher, iouDesfazer, iouRanking, iouSobreviventes, iouNovaRodada,
    PAPEIS, ROTULO_PAPEL, ACOES_PAPEL, podeEditar, ehDono, acoesSobre, transicaoPermitida
  };
  if (typeof module !== "undefined" && module.exports) module.exports = Logica;
  raiz.Logica = Logica;
})(typeof window !== "undefined" ? window : globalThis);
