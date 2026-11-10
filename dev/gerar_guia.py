"""Gera docs/guia-de-implantacao.html a partir de dev/guia_template.html e do supabase.sql da raiz.
Rode depois de mudar o supabase.sql:  python3 dev/gerar_guia.py"""
import html, os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
modelo = open(os.path.join(RAIZ, "dev", "guia_template.html"), encoding="utf-8").read()
sql = open(os.path.join(RAIZ, "supabase.sql"), encoding="utf-8").read()
exemplo = '''window.PRATO_CONFIG = {
  supabaseUrl: "https://abcdefghijklmnop.supabase.co",
  supabaseKey: "sb_publishable_Xy12AbCdEfGh34IjKlMn_5OpQrSt"
};'''
saida = modelo.replace("{{SQL}}", html.escape(sql, quote=False)).replace("{{CONFIG_EXEMPLO}}", html.escape(exemplo, quote=False))
assert "{{" not in saida, "sobrou marcador no modelo"
os.makedirs(os.path.join(RAIZ, "docs"), exist_ok=True)
open(os.path.join(RAIZ, "docs", "guia-de-implantacao.html"), "w", encoding="utf-8").write(saida)
print("docs/guia-de-implantacao.html gerado")
