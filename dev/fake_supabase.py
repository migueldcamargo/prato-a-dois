"""Servidor de TESTE que imita as rotas do Supabase usadas pelo app (auth anônima + PostgREST),
rodando sobre um Postgres local com o supabase.sql carregado. As consultas rodam com
SET ROLE authenticated + request.jwt.claims, então as regras de RLS valem de verdade.
Não tem Realtime: o app cai sozinho na releitura periódica (pollMs no config de teste).

Uso:  python3 dev/fake_supabase.py [pasta_do_site] [porta] [sufixo_da_url]
      (padrão: raiz do repositório, 8787, sem sufixo). Banco: variável PRATO_DSN."""
import base64, json, os, re, sys, threading, time, uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qsl, unquote
import psycopg
from psycopg import sql

SITE = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8787
SUFIXO = sys.argv[3] if len(sys.argv) > 3 else ""
DSN = os.environ.get("PRATO_DSN", "host=/tmp port=54329 user=postgres dbname=prato")
conn = psycopg.connect(DSN)
LOCK = threading.Lock()

def load_meta():
    with conn.cursor() as c:
        c.execute("""select c.relname, a.attname, format_type(a.atttypid, a.atttypmod)
                     from pg_attribute a join pg_class c on c.oid = a.attrelid join pg_namespace n on n.oid = c.relnamespace
                     where n.nspname = 'public' and c.relkind = 'r' and a.attnum > 0 and not a.attisdropped""")
        cols = {}
        for t, col, typ in c.fetchall(): cols.setdefault(t, {})[col] = typ
        c.execute("""select c.relname, array_agg(a.attname order by array_position(i.indkey, a.attnum))
                     from pg_index i join pg_class c on c.oid = i.indrelid join pg_namespace n on n.oid = c.relnamespace
                     join pg_attribute a on a.attrelid = c.oid and a.attnum = any(i.indkey)
                     where n.nspname = 'public' and i.indisprimary group by c.relname""")
        pks = {t: list(a) for t, a in c.fetchall()}
        c.execute("""select p.proname, p.proargnames, array(select format_type(x, null) from unnest(p.proargtypes) x), format_type(p.prorettype, null)
                     from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public'""")
        fns = {r[0]: (r[1] or [], r[2], r[3]) for r in c.fetchall()}
    conn.commit()
    return cols, pks, fns
COLS, PKS, FNS = load_meta()

def b64(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
def make_session(uid):
    now = int(time.time()); exp = now + 3600
    tok = b64({"alg": "HS256", "typ": "JWT"}) + "." + b64({"sub": uid, "role": "authenticated", "aud": "authenticated", "iat": now, "exp": exp, "is_anonymous": True, "session_id": str(uuid.uuid4())}) + ".c2ln"
    user = {"id": uid, "aud": "authenticated", "role": "authenticated", "is_anonymous": True, "app_metadata": {"provider": "anonymous"}, "user_metadata": {}, "identities": [], "created_at": "2026-11-09T00:00:00Z"}
    return {"access_token": tok, "token_type": "bearer", "expires_in": 3600, "expires_at": exp, "refresh_token": "rt-" + uid, "user": user}
def claims_from(headers):
    a = headers.get("Authorization", "")
    if a.startswith("Bearer ") and a.count(".") == 2:
        try:
            p = a[7:].split(".")[1]; p += "=" * (-len(p) % 4)
            return json.loads(base64.urlsafe_b64decode(p))
        except Exception: pass
    return None

def parse_val(v):
    v = v.strip()
    if v.startswith('"') and v.endswith('"'): v = v[1:-1]
    return v
def build_where(t, params):
    parts, args = [], []
    for k, v in params:
        if k in ("select", "columns", "on_conflict", "order", "limit", "offset"): continue
        if k not in COLS[t]: continue
        typ = COLS[t][k]
        op, _, val = v.partition(".")
        ident = sql.Identifier(k)
        if op == "eq": parts.append(sql.SQL("{} = %s::" + typ).format(ident)); args.append(parse_val(val))
        elif op == "neq": parts.append(sql.SQL("{} <> %s::" + typ).format(ident)); args.append(parse_val(val))
        elif op == "in":
            items = [parse_val(x) for x in re.findall(r'"[^"]*"|[^,()]+', val.strip("()"))]
            if not items: parts.append(sql.SQL("false")); continue
            parts.append(sql.SQL("{} in (" + ",".join(["%s::" + typ] * len(items)) + ")").format(ident)); args.extend(items)
        elif op == "is" and val == "null": parts.append(sql.SQL("{} is null").format(ident))
        else: raise ValueError("filtro não suportado: " + v)
    return (sql.SQL(" and ").join(parts) if parts else sql.SQL("true")), args
def sel_cols(t, params):
    s = dict(params).get("select", "*")
    if s.strip() == "*": return sql.SQL("*")
    return sql.SQL(", ").join(sql.Identifier(c.strip()) for c in s.split(","))

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body=None, ctype="application/json"):
        data = b"" if body is None else (body if isinstance(body, bytes) else body.encode())
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if data: self.wfile.write(data)
    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"null") if n else None

    def do_GET(self): self.route("GET")
    def do_POST(self): self.route("POST")
    def do_PATCH(self): self.route("PATCH")
    def do_DELETE(self): self.route("DELETE")

    def route(self, method):
        u = urlparse(self.path)
        if u.path.startswith("/auth/v1/"): return self.auth(method, u)
        if u.path.startswith("/rest/v1/"): return self.rest(method, u)
        if u.path.startswith("/realtime/"): return self.send(404, '{"message":"sem realtime no teste"}')
        if method != "GET": return self.send(405)
        p = u.path.lstrip("/") or "index.html"
        if p == "config.js":
            return self.send(200, 'window.PRATO_CONFIG = {supabaseUrl: "http://127.0.0.1:%d%s", supabaseKey: "sb_publishable_teste", pollMs: 1200};' % (PORT, SUFIXO), "application/javascript")
        fp = os.path.join(SITE, p)
        if not os.path.isfile(fp): return self.send(404, "not found", "text/plain")
        ct = {"html": "text/html; charset=utf-8", "js": "application/javascript", "png": "image/png", "webmanifest": "application/manifest+json"}.get(p.rsplit(".", 1)[-1], "application/octet-stream")
        return self.send(200, open(fp, "rb").read(), ct)

    def auth(self, method, u):
        b = self.body() if method == "POST" else None
        if u.path == "/auth/v1/signup": return self.send(200, json.dumps(make_session(str(uuid.uuid4()))))
        if u.path == "/auth/v1/token":
            rt = (b or {}).get("refresh_token", "")
            return self.send(200, json.dumps(make_session(rt[3:]))) if rt.startswith("rt-") else self.send(400, '{"error":"invalid_grant"}')
        if u.path == "/auth/v1/user":
            c = claims_from(self.headers)
            return self.send(200, json.dumps(make_session(c["sub"])["user"])) if c else self.send(401, "{}")
        if u.path == "/auth/v1/logout": return self.send(204)
        return self.send(404, "{}")

    def rest(self, method, u):
        c = claims_from(self.headers)
        role = "authenticated" if c else "anon"
        params = parse_qsl(u.query, keep_blank_values=True)
        prefer = self.headers.get("Prefer", "")
        single = "vnd.pgrst.object" in self.headers.get("Accept", "")
        want_rows = "return=representation" in prefer
        name = u.path[len("/rest/v1/"):]
        payload = self.body() if method in ("POST", "PATCH") else None
        try:
            with LOCK:
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute("select set_config('request.jwt.claims', %s, true)", [json.dumps(c or {"role": "anon"})])
                        cur.execute(sql.SQL("set local role {}").format(sql.Identifier(role)))
                        if name.startswith("rpc/"): return self.rpc(cur, name[4:], payload or {})
                        t = name
                        if t not in COLS: return self.send(404, json.dumps({"code": "42P01", "message": "tabela não existe"}))
                        where, wargs = build_where(t, params)
                        cols = sel_cols(t, params)
                        tid = sql.Identifier("public", t)
                        if method == "GET":
                            q = sql.SQL("select coalesce(json_agg(_r), '[]'::json) from (select {} from {} where {}) _r").format(cols, tid, where); args = wargs
                        elif method == "POST":
                            rows = payload if isinstance(payload, list) else [payload]
                            colnames = []
                            for r in rows:
                                for k in r:
                                    if k not in colnames: colnames.append(k)
                            cl = sql.SQL(", ").join(sql.Identifier(k) for k in colnames)
                            ins = sql.SQL("insert into {} ({}) select {} from json_populate_recordset(null::{}, %s::json)").format(tid, cl, cl, tid)
                            if "resolution=merge-duplicates" in prefer:
                                conflict = dict(params).get("on_conflict")
                                ccols = [x.strip() for x in conflict.split(",")] if conflict else PKS[t]
                                upd = [k for k in colnames if k not in ccols]
                                ins = ins + sql.SQL(" on conflict ({}) do ").format(sql.SQL(", ").join(sql.Identifier(k) for k in ccols)) + (
                                    sql.SQL("update set ") + sql.SQL(", ").join(sql.SQL("{} = excluded.{}").format(sql.Identifier(k), sql.Identifier(k)) for k in upd) if upd else sql.SQL("nothing"))
                            q = sql.SQL("with _w as ({} returning *) select coalesce(json_agg(_r), '[]'::json) from (select {} from _w) _r").format(ins, cols); args = [json.dumps(rows)]
                        elif method == "PATCH":
                            ks = list(payload.keys())
                            cl = sql.SQL(", ").join(sql.Identifier(k) for k in ks)
                            upd = sql.SQL("update {} set ({}) = (select {} from json_populate_record(null::{}, %s::json)) where {}").format(tid, cl, cl, tid, where)
                            q = sql.SQL("with _w as ({} returning *) select coalesce(json_agg(_r), '[]'::json) from (select {} from _w) _r").format(upd, cols); args = [json.dumps(payload)] + wargs
                        elif method == "DELETE":
                            dl = sql.SQL("delete from {} where {}").format(tid, where)
                            q = sql.SQL("with _w as ({} returning *) select coalesce(json_agg(_r), '[]'::json) from (select {} from _w) _r").format(dl, cols); args = wargs
                        cur.execute(q, args)
                        out = cur.fetchone()[0]
            if method == "GET" or want_rows or single:
                if single:
                    if len(out) != 1: return self.send(406, json.dumps({"code": "PGRST116", "message": "JSON object requested, multiple (or no) rows returned", "details": f"{len(out)} rows"}))
                    return self.send(200, json.dumps(out[0]))
                return self.send(200, json.dumps(out))
            return self.send(201 if method == "POST" else 204)
        except psycopg.Error as e:
            st = e.sqlstate or ""
            code = {"42501": 403 if c else 401, "23505": 409, "23503": 409}.get(st, 400)
            msg = e.diag.message_primary or str(e)
            if st == "42501" and "row-level security" not in msg and "permission denied" not in msg: msg = "permission denied: " + msg
            return self.send(code, json.dumps({"code": st, "message": msg, "details": None, "hint": None}))

    def rpc(self, cur, fn, args):
        if fn not in FNS: return self.send(404, json.dumps({"code": "PGRST202", "message": "função não existe"}))
        names, types, ret = FNS[fn]
        parts, vals = [], []
        for n, ty in zip(names, types):
            if n in args:
                parts.append(sql.SQL("{} => %s::" + ty).format(sql.Identifier(n))); vals.append(args[n] if not isinstance(args[n], (dict, list)) else json.dumps(args[n]))
        call = sql.SQL("{}({})").format(sql.Identifier("public", fn), sql.SQL(", ").join(parts))
        if ret == "void":
            cur.execute(sql.SQL("select {}").format(call), vals); return self.send(200, "null")
        cur.execute(sql.SQL("select to_json({})").format(call), vals)
        return self.send(200, json.dumps(cur.fetchone()[0]))

print(f"servidor de teste em http://127.0.0.1:{PORT}", flush=True)
ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
