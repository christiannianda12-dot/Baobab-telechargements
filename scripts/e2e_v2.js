// E2E v2 : explorateur, Centre de données, recherche rapide, graphiques. Prérequis : API :8000 et `next start` :3000 sur une base
// déjà alimentée (ex. 4 saisons de Premier League importées), sans compte créé.
const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const p = global.P = await b.newPage({ viewport: { width: 1100, height: 900 } });
  const go = async (path, sel) => { await p.goto("http://localhost:3000" + path); if (sel) await p.waitForSelector(sel, { timeout: 20000 }); };
  await p.goto("http://localhost:3000/register");
  await p.fill("[name=display_name]", "Owner"); await p.fill("[name=email]", "owner@example.com"); await p.fill("[name=password]", "motdepasse-solide-1");
  await p.click("button:has-text(\"S'inscrire\")"); await p.waitForURL("**/dashboard");
  await p.waitForFunction(() => /1\s?230/.test(document.querySelector("main")?.innerText ?? ""), null, { timeout: 20000 });
  console.log("1 tableau de bord : 1 230 matchs, prochains matchs/résultats OK");
  await go("/leagues", "text=Premier League (Angleterre)"); await p.click("a:has-text('Premier League (Angleterre)')");
  await p.waitForSelector("text=Classement calculé"); const rows = await p.locator("table tbody tr").count();
  if (rows < 15) throw new Error("classement trop court : " + rows); console.log(`2 classement : ${rows} équipes OK`);
  await p.selectOption("select[aria-label=Saison]", { index: 1 }); await p.waitForSelector("text=Classement calculé");
  const first = (await p.locator("table tbody tr").first().innerText()).replace(/\s+/g, " "); console.log("   saison précédente, 1er :", first.slice(0, 60));
  await p.click("table tbody tr:first-child a"); await p.waitForSelector("text=Classement Elo"); console.log("3 fiche équipe (Elo, forme, résultats) OK");
  await go("/matches", "h1:has-text('Matchs')"); await p.click("button:text-is('Résultats')"); await p.fill("input[aria-label=Équipe]", "arsenal");
  await p.waitForSelector("text=Arsenal", { timeout: 15000 }); await p.waitForSelector("text=sur"); console.log("4 explorateur : filtre équipe + pagination OK");
  await p.click("ul li:first-child a"); await p.waitForSelector("[role=tablist]"); await p.click("button[role=tab]:has-text('Cotes')");
  await p.waitForSelector("text=Cotes saisies"); await p.click("button[role=tab]:has-text('Forme')"); await p.waitForSelector("text=Forme et confrontations"); console.log("5 détail d'un match : onglets OK");
  await go("/data", "text=Centre de données"); await p.waitForSelector("text=Championnats principaux"); await p.waitForSelector("text=Brésil");
  const cards = await p.locator("button:text-is('Ajouter')").count(); if (cards < 30) throw new Error("catalogue incomplet : " + cards);
  await p.click("button:text-is('Ajouter') >> nth=0"); await p.waitForSelector("[role=dialog]"); await p.click("button:text-is('Annuler')"); await p.waitForSelector("[role=dialog]", { state: "detached" });
  console.log(`6 catalogue : ${cards} championnats, confirmation avant téléchargement OK`);
  await p.click("button[role=tab]:has-text('Qualité')"); await p.waitForSelector("text=Couverture par saison"); console.log("7 rapport de qualité OK");
  await p.click("button[role=tab]:has-text('Équipes')"); await p.waitForSelector("text=Nettoyer les équipes sans match"); console.log("8 doublons d'équipes OK");
  await p.click("button[role=tab]:has-text('Importer')"); await p.waitForSelector("text=Tout-ou-rien"); console.log("9 import multi-fichiers (écran) OK");
  await go("/dashboard", "h1:has-text('Tableau de bord')"); await p.keyboard.press("Control+k"); await p.waitForSelector("[role=dialog][aria-label='Recherche rapide']");
  await p.fill("input[aria-label=Rechercher]", "chels"); await p.waitForSelector("[role=option]:has-text('Chelsea')"); await p.keyboard.press("Enter");
  await p.waitForSelector("h1:has-text('Chelsea')"); console.log("10 recherche rapide Ctrl+K → fiche Chelsea OK");
  await go("/reliability", "text=Verdict"); await p.waitForSelector("text=Calibration"); const svgs = await p.locator("svg[role=img]").count();
  if (svgs < 3) throw new Error("graphiques manquants : " + svgs); console.log(`11 fiabilité : ${svgs} graphiques OK`);
  await b.close();
})().catch(async (e) => { try { console.error("URL", global.P.url(), "|", (await global.P.innerText("body")).slice(0, 300).replace(/\n+/g, " | ")); } catch {} console.error("ÉCHEC", e.message.split("\n")[0]); process.exit(1); });
