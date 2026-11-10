// Prato a Dois · service worker
// Sempre busca a versão nova na internet. Só usa a cópia guardada quando o celular está sem conexão.
// Ao mudar qualquer arquivo listado abaixo, suba o número do cache (e APP_VERSAO no index.html).
const CACHE = "prato-a-dois-v2";
const ARQUIVOS = ["./", "./index.html", "./logica.js", "./config.js", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./apple-touch-icon.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ARQUIVOS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  if (new URL(req.url).origin !== self.location.origin) return; // Supabase e biblioteca passam direto
  e.respondWith(
    fetch(req)
      .then(res => {
        if (res && res.ok) { const copia = res.clone(); caches.open(CACHE).then(c => c.put(req, copia)).catch(() => {}); }
        return res;
      })
      .catch(() => caches.match(req).then(r => r || caches.match("./index.html")))
  );
});
