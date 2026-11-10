"""Teste ponta a ponta do Prato a Dois: dois "celulares" (navegadores isolados) contra o servidor de teste.
Pré-requisitos (ver README.md, seção Desenvolvimento):
  1. Postgres local com o banco recriado:   dev/reset_db.sh
  2. Servidor de teste rodando:             python3 dev/fake_supabase.py
  3. Dependências: pip install playwright psycopg[binary]; cd dev && npm install
Rodar:  python3 dev/e2e.py      (CHROME=/caminho/do/chrome se o Playwright não tiver o dele)
Telas de conferência ficam em dev/saida/."""
import base64, io, json, os, subprocess, sys, time
from playwright.sync_api import sync_playwright
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("BASE", "http://127.0.0.1:8787/")
SBJS = os.path.join(AQUI, "node_modules/@supabase/supabase-js/dist/umd/supabase.js")
SAIDA = os.path.join(AQUI, "saida"); os.makedirs(SAIDA, exist_ok=True)
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")
PSQL = ["psql", "-h", os.environ.get("PGHOST", "/tmp"), "-p", os.environ.get("PGPORT", "54329"), "-U", os.environ.get("PGUSER", "postgres"), "-d", os.environ.get("PRATO_DB", "prato"), "-tAc"]
results = []

def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ((" — " + str(extra)) if extra else ""), flush=True)
def sqlq(qs): return subprocess.run(PSQL + [qs], capture_output=True, text=True).stdout.strip()
def ctx(browser, **kw):
    c = browser.new_context(**kw)
    c.route("https://cdn.jsdelivr.net/**", lambda r: r.fulfill(path=SBJS, content_type="application/javascript"))
    return c
def page_of(c, tag):
    p = c.new_page()
    p.on("pageerror", lambda e: print(f"[{tag}] ERRO NA PÁGINA:", e))
    p.goto(BASE)
    return p
def onboard(p, nome):
    p.wait_for_selector("#onbName"); p.fill("#onbName", nome); p.click("#onbForm button[type=submit]"); p.wait_for_selector(".home-hello")
def ultima_folha(p): return ".sheet-wrap:last-of-type"
def save_form(p):
    p.click('.sheet-foot [data-x="save"]')
    p.wait_for_function("!document.querySelector('.sheet .sheet-foot [data-x=\"save\"]')", timeout=10000)
def new_prato(p, nome, origem="casa", cats=(), nota=None, rest=None, quiz=None, foto=None):
    p.click(".fab-add"); p.wait_for_selector("#fNome")
    p.fill("#fNome", nome)
    p.click(f'[data-x="orig"][data-v="{origem}"]')
    if rest: p.fill("#fRest", rest)
    for c in cats: p.click(f'#fCats [data-x="cat"]:has-text("{c}")')
    if foto: p.set_input_files("#fGal", foto); p.wait_for_selector(".foto-prev img", timeout=8000)
    if nota: p.click(f'#fNota [data-n="{nota}"]')
    if quiz:
        p.click('[data-x="quizToggle"]')
        for k, v in quiz.items(): p.click(f'[data-x="qa"][data-attr="{k}"][data-v="{v}"]')
    save_form(p)
def aba(p, nome): p.click(f'[data-act="tab"][data-tab="{nome}"]'); time.sleep(0.3)
def pool(p): return p.inner_text("#poolCount")

img = Image.new("RGB", (1600, 1200), (200, 120, 40)); buf = io.BytesIO(); img.save(buf, "JPEG", quality=95)
FOTO = os.path.join(SAIDA, "foto_teste.jpg"); open(FOTO, "wb").write(buf.getvalue())

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME if os.path.exists(CHROME) else None, args=["--no-sandbox"])
    # ---------- Tutorial, zoom e rotação ----------
    iphone = dict(pw.devices["iPhone 13"]); iphone.pop("default_browser_type", None)
    ci = ctx(browser, **iphone); pi = page_of(ci, "iphone")
    pi.wait_for_selector(".tut-steps", timeout=10000)
    steps = pi.inner_text(".tut-steps")
    check("Tutorial abre sozinho no 1º acesso (iPhone)", "Adicionar à Tela de Início" in steps and "Compartilhar" in steps and "⋯" in steps)
    pi.click('[data-x="plat"][data-v="android"]')
    check("Tutorial tem a aba Android", "Instalar app" in pi.inner_text(".tut-steps"))
    pi.click('.tut-foot [data-x="close"]'); time.sleep(0.4)
    meta = pi.get_attribute('meta[name="viewport"]', "content")
    check("Zoom bloqueado", "user-scalable=no" in meta and pi.evaluate("getComputedStyle(document.documentElement).touchAction") == "manipulation")
    pi.reload(); pi.wait_for_selector("#onbName"); time.sleep(0.8)
    check("Tutorial não reabre sozinho depois de fechado", pi.locator(".tut-steps").count() == 0)
    ci.close()
    cl = ctx(browser, viewport={"width": 844, "height": 390}, is_mobile=True, has_touch=True, user_agent=iphone["user_agent"])
    pl = page_of(cl, "deitado"); pl.wait_for_timeout(800)
    check("Celular deitado mostra 'Gire o celular para a vertical'", pl.evaluate("getComputedStyle(document.querySelector('.rotate')).display") == "flex")
    cl.close()

    # ---------- Checklist com dois aparelhos ----------
    cA = ctx(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2); A = page_of(cA, "A")
    onboard(A, "Miguel Camargo")
    check("Início sem frases de apoio nos botões", A.locator(".hact small").count() == 0)
    check("Botão de sair escrito só 'Sair'", A.inner_text('.link-btn[data-act="sair"]').strip() == "Sair")
    A.click('[data-act="create"]'); A.fill("#crName", "Nosso cantinho"); A.click("#crBtn")
    A.wait_for_selector(".code-big", timeout=10000)
    code = A.inner_text(".code-big").replace("\n", "").strip()
    check("Código de 5 caracteres sem ambíguos", len(code) == 5 and all(c in "ABCDEFGHJKMNPQRSTUVWXYZ23456789" for c in code), code)
    A.click('[data-x="open"]'); A.wait_for_selector(".empty", timeout=10000)
    check("Navegação com 4 abas (Cardápio, O que comer, Histórico, Configurações)", A.locator(".bnav button").count() == 4 and "O que comer" in A.inner_text(".bnav"))
    check("Sem botão flutuante 'O que vamos comer?'", A.locator(".fab-quiz").count() == 0 and A.locator(".fab-add").count() == 1)
    new_prato(A, "Lamen", "casa", ["Asiática", "Sopas", "Massas"], nota=3, foto=FOTO)
    new_prato(A, "Pizza do Bela", "restaurante", ["Pizza"], rest="Bela Macerati", quiz={"tempo": "rapido", "peso": "encorpado"})
    A.wait_for_function("document.querySelectorAll('.dish').length >= 4", timeout=10000)
    secs = A.eval_on_selector_all(".sec", "els => els.map(e => [e.dataset.cat, [...e.querySelectorAll('.dish-name')].map(n => n.textContent)])")
    catnames = dict(l.split("|") for l in sqlq(f"select id||'|'||nome from categorias where cardapio='{code}'").splitlines())
    check("Lamen aparece nas abas Asiática, Sopas e Massas", sorted(catnames.get(c, c) for c, n in secs if "Lamen" in n) == ["Asiática", "Massas", "Sopas"])
    foto = sqlq("select data from fotos f join pratos p on p.id=f.prato_id where p.nome='Lamen'")
    check("Foto reduzida para até 400 px e salva", foto.startswith("data:image/jpeg;base64,") and max(Image.open(io.BytesIO(base64.b64decode(foto.split(",", 1)[1]))).size) <= 400)

    cB = ctx(browser, viewport={"width": 390, "height": 844}, device_scale_factor=2); B = page_of(cB, "B")
    onboard(B, "Ana")
    B.click('[data-act="join"]'); B.type("#joinCode", code.lower())
    check("Código em minúsculas vira maiúsculas", B.input_value("#joinCode") == code)
    B.click("#joinBtn"); B.wait_for_selector(".cover-name", timeout=10000)
    B.wait_for_function("document.querySelectorAll('.dish').length >= 4", timeout=10000)
    check("Outro aparelho vê os mesmos pratos", set(B.eval_on_selector_all(".dish-name", "e => e.map(x => x.textContent)")) == {"Lamen", "Pizza do Bela"})
    check("Leitor não vê + nem + de categoria", B.locator(".fab-add").count() == 0 and B.locator(".ctab-add").count() == 0)
    B.click('.dish:has-text("Lamen")'); B.wait_for_selector(".det-name")
    check("Leitor não vê estrelas, editar nem 'Fizemos hoje'", B.locator('[data-act="rate"]').count() + B.locator('[data-act="edit"]').count() + B.locator('[data-act="done"]').count() == 0)
    B.click(".det-close"); time.sleep(0.4)
    B.click('[data-act="request-edit"]')
    A.wait_for_function("document.querySelector('#banners') && document.querySelector('#banners').textContent.includes('1 pedido')", timeout=10000)
    check("Dono vê aviso e contador de pedidos", A.locator(".nav-badge").inner_text() == "1")
    A.click('[data-act="goto-config"]'); A.click('[data-act="papel"][data-acao="aprovar"]')
    B.wait_for_selector(".fab-add", timeout=10000)
    check("Depois de aprovado, editor vê o +", B.locator(".fab-add").count() == 1)
    B.click('.dish:has-text("Lamen")'); B.wait_for_selector('[data-act="rate"]', timeout=8000)
    B.click('[data-act="rate"][data-n="5"]')
    B.wait_for_function("document.querySelector('.rate-sum').textContent.includes('média 4,0')", timeout=8000)
    check("Notas 3 e 5 dão média 4,0", "Miguel Camargo 3" in B.inner_text(".rate-sum") and "Ana 5" in B.inner_text(".rate-sum"))
    B.click(".det-close"); time.sleep(0.4)

    aba(A, "cardapio"); A.wait_for_selector(".dish")
    A.click('.dish:has-text("Lamen") >> nth=0'); A.wait_for_selector('[data-act="done"]'); A.click('[data-act="done"]')
    A.wait_for_function("document.querySelector('.done-sum').textContent.includes('Feito 1 vez')", timeout=8000)
    check("'Fizemos hoje' atualiza contador e data, com Desfazer", "última vez em" in A.inner_text(".done-sum") and "Desfazer" in A.inner_text("#toast"))
    A.click(".det-close"); time.sleep(0.4)
    aba(A, "historico"); A.wait_for_selector(".rk-n", timeout=8000)
    check("Ranking do histórico mostra Lamen 1×", "Lamen" in A.inner_text(".tl-row:has(.rk-pos)") and "1×" in A.inner_text(".tl-row:has(.rk-pos)"))
    aba(A, "cardapio"); A.wait_for_selector(".dish")

    A.click(".fab-add"); A.wait_for_selector("#fNome"); B.click(".fab-add"); B.wait_for_selector("#fNome")
    for pg, nm, ori, cat in ((A, "Risoto de cogumelos", "casa", "Risoto"), (B, "Big Mac", "restaurante", "Hambúrguer")):
        pg.fill("#fNome", nm); pg.click(f'[data-x="orig"][data-v="{ori}"]'); pg.click(f'#fCats [data-x="cat"]:has-text("{cat}")')
    A.evaluate("document.querySelector('.sheet-foot [data-x=\"save\"]').click()")
    B.evaluate("document.querySelector('.sheet-foot [data-x=\"save\"]').click()")
    A.wait_for_function("[...document.querySelectorAll('.dish-name')].some(e => e.textContent === 'Big Mac')", timeout=10000)
    B.wait_for_function("[...document.querySelectorAll('.dish-name')].some(e => e.textContent === 'Risoto de cogumelos')", timeout=10000)
    check("Cadastros simultâneos não se apagam", sqlq(f"select count(*) from pratos where cardapio='{code}'") == "4")

    # ---------- Abre direto no cardápio ----------
    A.reload(); A.wait_for_selector(".cover-name", timeout=10000)
    check("Ao abrir o app, cai direto no último cardápio", A.locator(".home-hello").count() == 0 and A.inner_text(".cover-name") == "Nosso cantinho")

    # ---------- Atributo 'os dois' ----------
    A.click('.dish:has-text("Lamen") >> nth=0'); A.wait_for_selector('[data-act="edit"]'); A.click('[data-act="edit"]'); A.wait_for_selector("#fQuiz", state="attached")
    if A.locator("#fQuiz").is_hidden(): A.click('[data-x="quizToggle"]')
    check("Formulário tem 3 opções por atributo (A, Os dois, B)", A.locator('#fQuiz [data-attr="tempo"]').count() == 3 and A.locator('#fQuiz [data-attr="tempo"][data-v="ambos"]').inner_text() == "Os dois")
    A.click('[data-x="qa"][data-attr="tempo"][data-v="ambos"]'); A.click('[data-x="qa"][data-attr="peso"][data-v="leve"]')
    save_form(A); time.sleep(0.5)
    check("'Os dois' salvo no banco", sqlq("select tempo||'|'||peso from pratos where nome='Lamen'") == "ambos|leve")
    check("Detalhe mostra 'Tempo médio'", "Tempo médio" in A.inner_text(".det-body"))
    A.click(".det-close"); time.sleep(0.3)

    # ---------- Aba O que comer: filtros ----------
    aba(A, "decidir"); A.wait_for_selector("#poolCount")
    check("Sem filtro, todos no páreo", pool(A) == "4 pratos no páreo")
    A.click('[data-act="filt"][data-k="origem"][data-v="casa"]')
    check("Filtro Em casa", pool(A) == "2 pratos no páreo")
    A.click('[data-act="filt-mais"]'); A.click('[data-act="filt"][data-k="tempo"][data-v="rapido"]')
    check("'Os dois' e sem resposta passam no filtro Rápido", pool(A) == "2 pratos no páreo")
    A.click('[data-act="filt"][data-k="peso"][data-v="encorpado"]')
    check("Quem contradiz sai (Lamen é leve)", pool(A) == "1 prato no páreo")
    A.click('[data-act="filt"][data-k="peso"][data-v=""]'); A.click('[data-act="filt"][data-k="tempo"][data-v=""]')
    time.sleep(0.5); A.screenshot(path=os.path.join(SAIDA, "decidir.png"))

    # ---------- Duelo de categorias (Em casa) ----------
    A.click('[data-act="jogo-categorias"]'); A.wait_for_selector(".vs-q")
    check("Duelo começa com as categorias que têm pratos", A.inner_text(".vs-q") == "Massas ou Risoto?", A.inner_text(".vs-q"))
    time.sleep(0.5); A.screenshot(path=os.path.join(SAIDA, "duelo.png"))
    A.click('[data-x="desafiante"]'); A.wait_for_function("document.querySelector('.vs-q').textContent === 'Risoto ou Asiática?'")
    A.click('[data-x="os-dois"]'); A.wait_for_function("document.querySelector('.vs-q').textContent === 'Risoto e Asiática ou Sopas?'")
    check("'Tanto faz' mantém os dois como campeões", True)
    A.click('[data-x="campeao"]'); A.wait_for_selector(".vs-scroll h2")
    res = A.inner_text(".vs-scroll")
    check("Resultado: Risoto e Asiática, com Lamen e Risoto", "Hoje é dia de Risoto e Asiática" in res and "Lamen" in res and "Risoto de cogumelos" in res)
    A.click('[data-x="desfazer"]')
    check("Desfazer volta à última pergunta", A.inner_text(".vs-q") == "Risoto e Asiática ou Sopas?")
    A.click('[data-x="campeao"]'); A.wait_for_selector(".vs-scroll h2")
    A.click('[data-x="iou"]'); A.wait_for_selector('.sheet-wrap:last-of-type .vs-q')
    check("Isso ou aquilo a partir do resultado (1 par)", A.inner_text('.sheet-wrap:last-of-type .vs-q') == "Isso ou aquilo?")
    A.click('.sheet-wrap:last-of-type [data-x="cima"]'); A.wait_for_selector('.sheet-wrap:last-of-type .winner')
    check("Com um só restante, mostra o vencedor", "Vencedor" in A.inner_text('.sheet-wrap:last-of-type .winner') and A.locator('.sheet-wrap:last-of-type [data-x="rodada"]').is_disabled())
    A.click('.sheet-wrap:last-of-type [data-x="close"]'); time.sleep(0.4)
    A.click('.sheet-wrap:last-of-type [data-x="close"]'); time.sleep(0.4)

    # ---------- Isso ou aquilo com todos ----------
    A.click('[data-act="filt"][data-k="origem"][data-v=""]')
    A.click('[data-act="jogo-iou"]'); A.wait_for_selector(".vs-q")
    check("Isso ou aquilo: um prato em cima, um embaixo", A.locator(".vs-arena .vs-card").count() == 2 and A.inner_text(".qz-top .step") == "1 de 2")
    time.sleep(0.5); A.screenshot(path=os.path.join(SAIDA, "isso-ou-aquilo.png"))
    A.click('[data-x="cima"]'); time.sleep(0.2)
    A.click('[data-x="os-dois"]'); A.wait_for_selector(".rk-sec")
    txt = A.eval_on_selector(".vs-scroll", "e => e.textContent")
    check("Ranking separa ganhou, foi pro final e descartados", "Ganharam a disputa" in txt and "Foram pro final" in txt and "Descartados (1)" in txt)
    time.sleep(0.5); A.screenshot(path=os.path.join(SAIDA, "ranking.png"))
    check("Botão 'Jogar de novo só com estes (3)'", A.inner_text('[data-x="rodada"]') == "Jogar de novo só com estes (3)")
    A.click('[data-x="rodada"]'); A.wait_for_selector(".vs-q")
    par = A.eval_on_selector_all(".vs-arena .vs-card .vs-info > b", "e => e.map(x => x.textContent)")
    A.click('[data-x="baixo"]'); time.sleep(0.2); A.click('[data-x="desfazer"]'); time.sleep(0.2)
    check("Desfazer volta o mesmo par", A.eval_on_selector_all(".vs-arena .vs-card .vs-info > b", "e => e.map(x => x.textContent)") == par)
    A.click('[data-x="baixo"]'); A.wait_for_selector('[data-x="descarta"]')
    check("Prato sem par pergunta se fica ou sai", A.inner_text(".vs-q") == "Esse ficou sem par")
    A.click('[data-x="descarta"]'); A.wait_for_selector(".winner")
    check("Rodada 2 com o ranking chega num vencedor", "Rodada 2" in A.inner_text(".qz-top .step") and A.inner_text(".winner b") == par[1])
    A.click('[data-x="todos"]'); A.wait_for_selector(".vs-q")
    check("Recomeçar com todos volta aos 4 pratos", A.inner_text(".qz-top .step") == "1 de 2")
    A.click('[data-x="close"]'); time.sleep(0.4)

    # ---------- Classificação com 'os dois' ----------
    aba(A, "config"); A.click('.cfg-sec [data-act="classify"]')
    A.wait_for_selector('[data-x="start"][data-attr="ocasiao"]'); A.click('[data-x="start"][data-attr="ocasiao"]'); A.wait_for_selector(".sw-card.front")
    first = A.inner_text(".sw-card.front .sw-info b")
    box = A.locator(".sw-card.front").bounding_box(); cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    A.mouse.move(cx, cy); A.mouse.down()
    for i in range(1, 13): A.mouse.move(cx - i * 15, cy + i * 2)
    tinted = A.eval_on_selector(".sw-card.front", "e => e.style.getPropertyValue('--ta')")
    A.mouse.up(); time.sleep(1.2)
    check("Arrasto inclina/colore e grava a 1ª opção", float(tinted or 0) > .5 and sqlq(f"select ocasiao from pratos where nome='{first}'") == "diadia")
    second = A.inner_text(".sw-card.front .sw-info b")
    A.click('[data-x="AB"]'); time.sleep(1.2)
    check("Botão 'Os dois' grava ambos", sqlq(f"select ocasiao from pratos where nome='{second}'") == "ambos")
    third = A.inner_text(".sw-card.front .sw-info b")
    A.click('[data-x="B"]'); time.sleep(1.2)
    check("Botão grava a 2ª opção", sqlq(f"select ocasiao from pratos where nome='{third}'") == "especial")
    A.click('[data-x="undo"]'); time.sleep(1.2)
    check("Desfazer último volta o card e apaga a resposta", A.inner_text(".sw-card.front .sw-info b") == third and sqlq(f"select coalesce(ocasiao,'vazio') from pratos where nome='{third}'") == "vazio")
    A.click('.sheet-wrap:last-of-type [data-x="close"]'); time.sleep(0.5)

    # ---------- Importar ----------
    aba(A, "cardapio"); A.wait_for_selector(".dish")
    A.click('.dish:has-text("Lamen") >> nth=0'); A.wait_for_selector('[data-act="edit"]'); A.click('[data-act="edit"]')
    A.wait_for_selector("#fCats"); A.click('[data-x="newCat"]'); A.fill("#fNewCat", "Caldos"); A.click('[data-x="newCatOk"]')
    A.wait_for_selector('#fCats [data-x="cat"][aria-pressed="true"]:has-text("Caldos")', timeout=8000)
    save_form(A); time.sleep(0.5); A.click(".det-close"); time.sleep(0.3)
    B.click('[data-act="home"]'); B.wait_for_selector(".home-hello")
    B.click('[data-act="create"]'); B.fill("#crName", "Cardápio da Ana"); B.click("#crBtn")
    B.wait_for_selector(".code-big", timeout=10000); code_b = B.inner_text(".code-big").replace("\n", "").strip()
    B.click('[data-x="open"]'); B.wait_for_selector(".empty", timeout=10000)
    B.click('[data-act="home"]'); B.wait_for_selector(".myitem", timeout=8000); B.wait_for_timeout(800)
    roles = B.eval_on_selector_all(".myitem", "e => e.map(x => x.textContent.replace(/\\s+/g,' ').trim())")
    check("Meus cardápios lista o papel em cada um", any("Nosso cantinho" in r and "Editor" in r for r in roles) and any("Cardápio da Ana" in r and "Dono" in r for r in roles), roles)
    B.click(f'.myitem[data-code="{code}"]'); B.wait_for_selector(".dish", timeout=10000)
    B.click('.dish:has-text("Lamen") >> nth=0'); B.wait_for_selector('[data-act="import"]'); B.click('[data-act="import"]')
    B.wait_for_selector(f'[data-x="to"][data-code="{code_b}"]', timeout=8000); B.click(f'[data-x="to"][data-code="{code_b}"]')
    B.wait_for_function("document.querySelector('#toast').textContent.includes('importado')", timeout=8000)
    imp = sqlq(f"select (select string_agg(c.nome, ',' order by c.nome) from categorias c where c.id = any(p.categorias)) || '|' || coalesce(p.tempo,'') || '|' || (select count(*) from notas n where n.prato_id=p.id) || '|' || (select count(*) from feitos f where f.prato_id=p.id) || '|' || (select count(*) from fotos f where f.prato_id=p.id) from pratos p where p.cardapio='{code_b}'")
    check("Importação leva categorias (cria Caldos), atributos e foto, sem notas nem histórico", imp == "Asiática,Caldos,Massas,Sopas|ambos|0|0|1", imp)

    # ---------- Papéis ----------
    aba(A, "config"); A.wait_for_selector(".cfg-sec")
    A.click('[data-act="papel"][data-acao="tornar_dono"]'); A.click('.sheet-wrap:last-of-type [data-x="ok"]'); time.sleep(1.0)
    check("Dono consegue tornar o par dono também", sqlq(f"select papel from membros where cardapio='{code}' and nome='Ana'") == "dono")
    A.wait_for_timeout(500)
    check("Sem botões de papel sobre outro dono", A.locator('.cfg-row:has-text("Ana") [data-act="papel"]').count() == 0)
    check("Rodapé mostra versão do app, do banco e a sincronização", "2.0.0" in A.inner_text(".foot-note") and "banco v2" in A.inner_text(".foot-note"))
    A.click('.cfg-link[data-act="tutorial"]'); A.wait_for_selector(".tut-steps")
    check("Tutorial abre pelas Configurações", A.locator(".tut-steps").count() == 1)
    A.click('.tut-foot [data-x="close"]'); time.sleep(0.4)

    # ---------- Sair ----------
    B.click(".det-close"); time.sleep(0.4)
    B.click('[data-act="tab"][data-tab="config"]'); B.wait_for_selector('.cfg-link[data-act="sair"]')
    B.click('.cfg-link[data-act="sair"]'); B.wait_for_selector(".dlg")
    check("Sair avisa sobre ser dono antes de sair", "torne seu par dono" in B.inner_text(".dlg"))
    B.click('.sheet-wrap:last-of-type [data-x="ok"]'); B.wait_for_selector("#onbName", timeout=10000)
    check("Depois de sair, volta para o primeiro acesso sem dados", B.evaluate("localStorage.getItem('pd:meus') === null && localStorage.getItem('pd:nome') === null"))

    aba(A, "cardapio"); A.evaluate("window.scrollTo(0,0)"); time.sleep(0.6)
    A.screenshot(path=os.path.join(SAIDA, "cardapio.png"))
    browser.close()

fails = [r for r in results if not r[1]]
print(f"\n{len(results) - len(fails)}/{len(results)} verificações passaram")
sys.exit(1 if fails else 0)
