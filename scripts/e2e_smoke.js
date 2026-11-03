// Test de bout en bout (Playwright). Prérequis : base vide migrée, API sur :8000, frontend (next start) sur :3000.
// Lancer : NODE_PATH=$(npm root -g) node scripts/e2e_smoke.js   (crée le compte administrateur "owner@example.com")
const { chromium } = require("playwright");
const assert = require("assert");
(async () => {
  const b = await chromium.launch(); const p = global.P = await b.newPage({ viewport: { width: 390, height: 800 } });
  const errs = []; p.on("pageerror", e => errs.push(e.message)); p.on("console", m => m.type()==="error" && errs.push(m.text()));
  await p.goto("http://localhost:3000/dashboard"); await p.waitForURL("**/login");
  console.log("1 redirect non connecté OK");
  await p.goto("http://localhost:3000/register");
  await p.fill("[name=display_name]", "Owner"); await p.fill("[name=email]", "owner@example.com"); await p.fill("[name=password]", "motdepasse-solide-1");
  await p.click("button:has-text(\"S'inscrire\")"); await p.waitForURL("**/dashboard");
  await p.waitForSelector("text=Aucun match enregistré aujourd");
  console.log("2 inscription + connexion + dashboard vide honnête OK");
  const leak = await p.evaluate(() => ({ cookie: document.cookie, ls: JSON.stringify(Object.entries(localStorage)) }));
  if (/predix_session=|eyJ/.test(leak.cookie + leak.ls)) throw new Error("jeton lisible par le JavaScript : " + JSON.stringify(leak));
  const ck = (await p.context().cookies()).find((c) => c.name === "predix_session");
  if (!ck || !ck.httpOnly || ck.sameSite !== "Lax") throw new Error("cookie de session absent ou mal configuré");
  console.log("2b cookie HttpOnly + SameSite=Lax, aucun jeton dans localStorage/document.cookie OK");
  await p.screenshot({ path: "/tmp/dash-mobile.png" });
  await p.goto("http://localhost:3000/admin"); await p.waitForSelector("text=Saisie manuelle");
  const add = async (ph, v, btn) => { await p.fill(`[placeholder="${ph}"]`, v); await p.click(`button:has-text("${btn}")`); await p.waitForSelector("text=ajouté"); };
  await add("Nom de l'équipe", "Alpha FC", "Ajouter l'équipe"); await add("Nom de l'équipe", "Beta United", "Ajouter l'équipe");
  await add("Compétition", "Coupe Test", "Ajouter la compétition");
  await p.selectOption("[name=c]", { label: "Coupe Test" }); await p.selectOption("[name=h]", { label: "Alpha FC" }); await p.selectOption("[name=a]", { label: "Beta United" });
  const d = new Date(); d.setHours(23, 30, 0, 0); const loc = new Date(d.getTime() - d.getTimezoneOffset()*60000).toISOString().slice(0,16);
  await p.fill("[name=k]", loc); await p.click("button:has-text('Ajouter le match')"); await p.waitForSelector("text=Match ajouté");
  console.log("3 saisie manuelle équipes/compétition/match OK");
  await p.goto("http://localhost:3000/matches"); await p.click("text=Alpha FC"); await p.waitForSelector("text=Aucune cote saisie");
  for (const [sel, price] of [["home","2.10"],["draw","3.40"],["away","3.60"]]) {
    await p.selectOption("[name=selection]", sel); await p.fill("[name=price]", price); await p.click("button:has-text('Ajouter la cote')");
    await p.waitForSelector(`td:text-is("${Number(price)}")`);
  }
  await p.waitForSelector("text=marge 4.8 %"); await p.waitForSelector("text=45.4 %");
  console.log("4 cotes + marge 4.8 % + proba corrigée 45.4 % OK");
  await p.waitForSelector("text=Prédiction non produite");
  for (const path of ["assistant","combos","history","performance","calendar","settings"]) { await p.goto("http://localhost:3000/"+path); await p.waitForSelector("h1"); }
  await p.goto("http://localhost:3000/settings"); await p.waitForSelector("text=API et base de données opérationnelles");
  await p.screenshot({ path: "/tmp/settings-mobile.png" });
  console.log("5 pages secondaires OK");
  await p.click("main >> text=Se déconnecter"); await p.waitForURL("**/login"); console.log("6 déconnexion OK");
  await p.fill("[name=email]", "owner@example.com"); await p.fill("[name=password]", "mauvais-mot-de-passe"); await p.click("button:has-text('Se connecter')");
  await p.waitForSelector("text=Identifiants incorrects"); console.log("7 erreur de connexion affichée OK");
  console.log("erreurs console:", errs.filter(e=>!/401|Failed to load resource/.test(e)));
  await b.close();
})().catch(async e => { try { await global.P.screenshot({path:"/tmp/fail.png"}); console.error("URL", global.P.url(), "BODY", (await global.P.innerText("body")).slice(0,400).replace(/\n+/g," | ")); } catch {}
  console.error(e.message.split("\n").slice(0,3).join(" / ")); console.error("ÉCHEC", e.message.split("\n")[0]); process.exit(1); });
