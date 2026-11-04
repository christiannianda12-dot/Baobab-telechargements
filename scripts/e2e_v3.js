// E2E v3 : coupes UEFA, combinés proposés, automatisation, aide. Prérequis : API :8000 + `next start` :3000 sur une base alimentée
// (championnat + coupes suivies), sans compte créé.
const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const p = global.P = await b.newPage({ viewport: { width: 1100, height: 900 } });
  const go = async (path, sel) => { await p.goto("http://localhost:3000" + path); if (sel) await p.waitForSelector(sel, { timeout: 25000 }); };
  await p.goto("http://localhost:3000/register");
  await p.fill("[name=display_name]", "Owner"); await p.fill("[name=email]", "owner@example.com"); await p.fill("[name=password]", "motdepasse-solide-1");
  await p.click("button:has-text(\"S'inscrire\")"); await p.waitForURL("**/dashboard");
  await p.waitForSelector("text=Prochains matchs, analysés"); await p.waitForSelector("text=Mise à jour automatique active", { timeout: 20000 });
  console.log("1 tableau de bord dynamique + barre d'état automatique OK");
  await go("/leagues", "text=UEFA Champions League"); await p.click("a:has-text('UEFA Champions League')"); await p.waitForSelector("text=Classement calculé");
  const rows = await p.locator("table tbody tr").count(); if (rows < 30) throw new Error("classement C1 trop court : " + rows);
  console.log(`2 Ligue des champions : classement de ${rows} équipes OK`);
  await go("/data", "text=Coupes européennes (UEFA)"); await p.waitForSelector("text=Ligue des champions"); await p.waitForSelector("text=Conference League");
  console.log("3 catalogue : coupes européennes présentes OK");
  await go("/combos", "text=Proposés pour vous"); await p.waitForSelector("text=meilleures cotes");
  for (const [tab, name] of [["Prudent", "prudent"], ["Ambitieux", "ambitieux"], ["Équilibré", "equilibre"]]) { await p.click(`button[role=tab]:text-is('${tab}')`); await p.waitForTimeout(700); }
  await p.waitForSelector("article, .card:has-text('Aucun')"); console.log("4 combinés proposés : 3 profils OK");
  await go("/settings", "text=Automatisation"); await p.waitForSelector("text=Enregistrer automatiquement les prédictions"); await p.waitForSelector("text=The Odds API");
  await p.click("button:has-text('Lancer maintenant')"); await p.waitForSelector("text=réussie", { timeout: 60000 });
  console.log("5 automatisation : exécution manuelle journalisée OK");
  await go("/help", "text=Valeur espérée"); console.log("6 aide et glossaire OK");
  await go("/reliability", "h1:has-text('Fiabilité')"); console.log("7 fiabilité (championnat) OK");
  await b.close();
})().catch(async (e) => { try { console.error("URL", global.P.url(), "|", (await global.P.innerText("body")).slice(0, 350).replace(/\n+/g, " | ")); } catch {} console.error("ÉCHEC", e.message.split("\n")[0]); process.exit(1); });
