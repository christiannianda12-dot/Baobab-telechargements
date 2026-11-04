// E2E PWA : manifeste valide, icônes, service worker actif, page hors ligne. Prérequis : API :8000 et `next start` :3000 (build de production).
const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 390, height: 800 } }); const p = global.P = await ctx.newPage();
  await p.goto("http://localhost:3000/login");
  const href = await p.getAttribute("link[rel=manifest]", "href"); if (!href) throw new Error("lien <link rel=manifest> absent");
  const m = await (await fetch("http://localhost:3000" + href)).json();
  const sizes = m.icons.map((i) => i.sizes);
  if (m.display !== "standalone" || m.start_url !== "/" || !sizes.includes("192x192") || !sizes.includes("512x512") || !m.icons.some((i) => i.purpose === "maskable")) throw new Error("manifeste incomplet : " + JSON.stringify(m));
  for (const i of m.icons) { const r = await fetch("http://localhost:3000" + i.src); if (!r.ok || !(r.headers.get("content-type") || "").includes("image/png")) throw new Error("icône KO " + i.src); }
  console.log("1 manifeste valide (standalone, icônes 192/512 PNG + maskable) OK");
  const sw = await p.evaluate(async () => { const r = await navigator.serviceWorker.ready; return r.active ? r.active.state : "none"; });
  if (sw !== "activated") throw new Error("service worker non actif : " + sw);
  console.log("2 service worker actif OK");
  await p.reload(); await p.waitForSelector("text=Connexion");   // le SW contrôle maintenant la page
  await ctx.setOffline(true);
  await p.goto("http://localhost:3000/dashboard").catch(() => {});
  await p.waitForSelector("text=Vous êtes hors ligne", { timeout: 8000 });
  console.log("3 hors ligne : page de repli affichée OK");
  await ctx.setOffline(false);
  const theme = await p.getAttribute("meta[name=theme-color]", "content"); const vp = await p.getAttribute("meta[name=viewport]", "content");
  if (!theme || !vp.includes("width=device-width")) throw new Error("meta theme-color/viewport manquants");
  console.log("4 theme-color + viewport mobile OK");
  await b.close();
})().catch(async (e) => { try { console.error("BODY", (await global.P.innerText("body")).slice(0, 300).replace(/\n+/g, " | ")); } catch {} console.error("ÉCHEC", e.message.split("\n")[0]); process.exit(1); });
