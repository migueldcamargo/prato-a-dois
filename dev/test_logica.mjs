// Testes da lógica pura (logica.js). Rode da raiz do repositório:  node dev/test_logica.mjs
import { createRequire } from "node:module";
import assert from "node:assert/strict";
const require = createRequire(import.meta.url);
const L = require("../logica.js");

let ok = 0;
const t = (nome, fn) => { fn(); ok++; console.log("ok  " + nome); };
const rngFixo = () => { let s = 7; return () => ((s = (s * 9301 + 49297) % 233280) / 233280); };
const prato = (id, extra = {}) => Object.assign({ id, nome: id, origem: "casa", categorias: [], quiz: {}, notas: {}, feitos: {} }, extra);

/* 1-2. Atributos e filtros */
t("'os dois' passa em qualquer filtro do atributo", () => {
  assert.equal(L.combina("ambos", "rapido"), "sim");
  assert.equal(L.combina("ambos", "elaborado"), "sim");
  assert.equal(L.combina("rapido", "elaborado"), "nao");
  assert.equal(L.combina(null, "rapido"), "talvez");
  assert.equal(L.combina("rapido", null), "sim");
});
t("filtro mantém sem resposta, tira quem contradiz e pontua quem bate", () => {
  const ps = [prato("a", { quiz: { tempo: "rapido" } }), prato("b", { quiz: { tempo: "ambos" } }), prato("c"), prato("d", { quiz: { tempo: "elaborado" } }), prato("e", { origem: "restaurante", quiz: { tempo: "rapido" } })];
  const r = L.filtrar(ps, { origem: "casa", tempo: "rapido" });
  assert.deepEqual(r.map(x => x.prato.id), ["a", "b", "c"]);
  assert.deepEqual(r.map(x => x.pontos), [2, 2, 1]);
  assert.equal(L.filtrosAtivos({ origem: "casa", tempo: null }), 1);
});
t("sugestões: bate mais > maior nota > mais tempo sem fazer", () => {
  const ps = [
    { prato: prato("x", { notas: { u: 3 } }), pontos: 2 },
    { prato: prato("y", { notas: { u: 5 } }), pontos: 2 },
    { prato: prato("z", { notas: { u: 5 } }), pontos: 4 },
    { prato: prato("w", { notas: { u: 5 }, feitos: { f: { d: "2026-11-01" } } }), pontos: 2 }
  ];
  assert.deepEqual(L.ordenarSugestoes(ps, "2026-11-10").map(x => x.prato.id), ["z", "y", "w", "x"]);
});
t("rótulos de 'os dois' existem para os 4 atributos", () => {
  L.ATRIBUTOS.forEach(a => assert.ok(L.ROTULO_VALOR[a.key + ":ambos"]));
  assert.deepEqual(L.VALORES_VALIDOS.tempo, ["rapido", "elaborado", "ambos"]);
});

/* 3. Duelo de categorias (exemplo do Miguel) */
t("duelo: hambúrguer ou pizza → pizza → risoto → asiática → os dois", () => {
  let s = L.dueloIniciar(["hamb", "pizza", "massa", "risoto", "asia", "japa"]);
  assert.equal(s.fase, "duelando"); assert.deepEqual(s.campeao, ["hamb"]); assert.equal(s.fila[0], "pizza");
  s = L.dueloEscolher(s, "desafiante");      // pizza
  s = L.dueloEscolher(s, "campeao");         // pizza x massa → pizza
  s = L.dueloEscolher(s, "desafiante");      // risoto
  s = L.dueloEscolher(s, "desafiante");      // asiática
  assert.equal(s.fase, "duelando");
  s = L.dueloEscolher(s, "os-dois");         // asiática + japonesa
  assert.equal(s.fase, "fim");
  assert.deepEqual(s.campeao, ["asia", "japa"]);
  assert.deepEqual(s.eliminadas.sort(), ["hamb", "massa", "pizza", "risoto"]);
  assert.equal(s.passo, 5); assert.equal(s.total, 5);
});
t("duelo: desfazer volta ao estado anterior exato", () => {
  const s0 = L.dueloIniciar(["a", "b", "c"]);
  const s1 = L.dueloEscolher(s0, "desafiante");
  assert.equal(L.dueloDesfazer(s1), s0);
  assert.equal(L.dueloDesfazer(s0), s0);
});
t("duelo: 0 ou 1 categoria já termina; escolha inválida dá erro", () => {
  assert.equal(L.dueloIniciar(["a"]).fase, "fim");
  assert.equal(L.dueloIniciar([]).fase, "fim");
  assert.throws(() => L.dueloEscolher(L.dueloIniciar(["a", "b"]), "x"));
});

/* 4. Isso ou aquilo */
t("isso ou aquilo: rodada completa, ranking e descartes", () => {
  let s = L.iouIniciar(["a", "b", "c", "d", "e"], { rng: rngFixo() });
  assert.equal(s.pares.length, 3); assert.equal(s.pares[2].length, 1);
  const [p1, p2, p3] = s.pares;
  s = L.iouEscolher(s, "cima");      // p1[0] ganha
  s = L.iouEscolher(s, "os-dois");   // p2 vai pro final
  assert.equal(s.fase, "jogando");
  assert.throws(() => L.iouEscolher(s, "cima"));   // sozinho só aceita fica/descarta
  s = L.iouEscolher(s, "descarta");
  assert.equal(s.fase, "ranking");
  const r = L.iouRanking(s);
  assert.deepEqual(r.ganharam, [p1[0]]);
  assert.deepEqual(r.final.sort(), p2.slice().sort());
  assert.deepEqual(r.descartados.sort(), [p1[1], p3[0]].sort());
});
t("isso ou aquilo: desfazer, nova rodada só com o ranking e recomeçar com todos", () => {
  let s = L.iouIniciar(["a", "b", "c", "d"], { rng: rngFixo() });
  const s0 = s;
  s = L.iouEscolher(s, "baixo");
  assert.equal(L.iouDesfazer(s), s0);
  s = L.iouEscolher(s, "os-dois");
  const vencedor = s.pares[0][1];
  const r2 = L.iouNovaRodada(s, "ranking", { rng: rngFixo() });
  assert.equal(r2.rodada, 2);
  assert.equal(r2.vitorias[vencedor], 1);
  assert.deepEqual([].concat(...r2.pares).sort(), [vencedor, ...s.pares[1]].sort());
  assert.deepEqual(r2.todos.sort(), ["a", "b", "c", "d"]);
  const tudo = L.iouNovaRodada(r2, "todos", { rng: rngFixo() });
  assert.equal(tudo.rodada, 1); assert.deepEqual(tudo.vitorias, {});
  assert.equal([].concat(...tudo.pares).length, 4);
});
t("isso ou aquilo: vitórias acumuladas ordenam o ranking", () => {
  let s = L.iouIniciar(["a", "b"], { rng: () => 0.99, vitorias: { b: 3, a: 1 } });
  s = L.iouEscolher(s, "os-dois");
  assert.deepEqual(L.iouRanking(s).final, ["b", "a"]);
  assert.equal(L.iouIniciar([]).fase, "ranking");
});

/* 5. Papéis */
t("papéis: só o dono age, nunca sobre si mesmo, e só pelas transições da tabela", () => {
  assert.deepEqual(L.acoesSobre("dono", "pendente", false), ["aprovar", "recusar"]);
  assert.deepEqual(L.acoesSobre("dono", "editor", false), ["tornar_dono", "tirar_edicao"]);
  assert.deepEqual(L.acoesSobre("dono", "leitor", false), ["remover"]);
  assert.deepEqual(L.acoesSobre("dono", "dono", false), []);
  assert.deepEqual(L.acoesSobre("dono", "editor", true), []);
  assert.deepEqual(L.acoesSobre("editor", "leitor", false), []);
  assert.ok(L.transicaoPermitida("pendente", "editor"));
  assert.ok(!L.transicaoPermitida("leitor", "dono"));
  assert.ok(!L.transicaoPermitida("dono", "leitor"));
});

console.log(`\n${ok} testes passaram`);
