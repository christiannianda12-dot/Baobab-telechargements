// E2E import CSV + analyse (Playwright). Prérequis identiques à e2e_smoke.js, sur une base VIDE.
const { chromium } = require("playwright");
const H = "date,competition,season,home_team,away_team,home_score,away_score,home_corners,away_corners\n";
const GOOD = H + ["2026-01-10,Ligue T,2025,Alpha,Beta,2,1,6,3", "2026-01-20,Ligue T,2025,Beta,Alpha,0,0,,", "2026-02-01,Ligue T,2025,Alpha,Gamma,3,0,7,"].join("\n") + "\n";
const BAD = H + "2026-01-10,Ligue T,2025,Alpha,Beta,2,1,6,3\nnot-a-date,Ligue T,2025,Alpha,Beta,1,1,,\n";
const buf = (t) => ({ name: "m.csv", mimeType: "text/csv", buffer: Buffer.from(t) });
(async () => {
  const b = await chromium.launch(); const p = global.P = await b.newPage({ viewport: { width: 390, height: 800 } });
  await p.goto("http://localhost:3000/register");
  await p.fill("[name=display_name]", "Owner"); await p.fill("[name=email]", "owner@example.com"); await p.fill("[name=password]", "motdepasse-solide-1");
  await p.click("button:has-text(\"S'inscrire\")"); await p.waitForURL("**/dashboard");
  await p.goto("http://localhost:3000/admin"); await p.waitForSelector("text=Import CSV");
  await p.setInputFiles("[name=file]", buf(BAD)); await p.click("button:text-is('Importer')");
  await p.waitForSelector("text=Ligne 3"); await p.waitForSelector("text=aucune ligne importée"); console.log("1 CSV invalide refusé, ligne 3 signalée OK");
  await p.setInputFiles("[name=file]", buf(GOOD)); await p.click("button:has-text('Vérifier sans importer')");
  await p.waitForSelector("text=Vérification réussie (rien écrit) : 3 match(s)"); console.log("2 vérification à blanc OK");
  await p.click("button:text-is('Importer')"); await p.waitForSelector("text=Import terminé : 3 match(s), 3 équipe(s)"); console.log("3 import OK");
  await p.click("button:text-is('Importer')"); await p.waitForSelector("text=0 match(s), 0 équipe(s)"); await p.waitForSelector("text=3 doublon(s)"); console.log("4 réimport idempotent OK");
  // match programmé créé via l'API (la saisie UI est déjà couverte par e2e_smoke)
  const tok = (await (await fetch("http://localhost:8000/api/v1/auth/login", { method: "POST", body: new URLSearchParams({ username: "owner@example.com", password: "motdepasse-solide-1" }) })).json()).access_token;
  const get = async (u) => (await fetch("http://localhost:8000/api/v1" + u)).json();
  const teams = Object.fromEntries((await get("/teams")).map((t) => [t.name, t.id])); const comp = (await get("/competitions"))[0].id;
  const m = await (await fetch("http://localhost:8000/api/v1/matches", { method: "POST", headers: { Authorization: "Bearer " + tok, "content-type": "application/json" },
    body: JSON.stringify({ competition_id: comp, home_team_id: teams.Alpha, away_team_id: teams.Beta, kickoff_at: "2026-03-01T20:00:00Z" }) })).json();
  await p.goto(`http://localhost:3000/matches/${m.id}`); await p.waitForSelector("text=Forme et confrontations directes");
  await p.waitForSelector("text=Alpha (domicile)"); await p.waitForSelector("text=Confrontations directes : 2 match(s)");
  await p.waitForSelector("text=minimum conseillé");
  const row = await p.locator("tr:has-text('Alpha (tous)')").innerText(); console.log("5 forme affichée :", row.replace(/\s+/g, " "));
  await b.close();
})().catch(async (e) => { try { console.error("BODY", (await global.P.innerText("body")).slice(0, 300).replace(/\n+/g, " | ")); } catch {} console.error("ÉCHEC", e.message.split("\n")[0]); process.exit(1); });
