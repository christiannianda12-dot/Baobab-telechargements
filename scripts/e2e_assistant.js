// E2E assistant + combinés. Prérequis : base VIDE migrée, API :8000, frontend :3000, /tmp/synth.csv (ligue SYNTHÉTIQUE des tests).
const { chromium } = require("playwright");
const API = "http://localhost:8000/api/v1";
(async () => {
  const b = await chromium.launch(); const p = global.P = await b.newPage({ viewport: { width: 390, height: 900 } });
  await p.goto("http://localhost:3000/register");
  await p.fill("[name=display_name]", "Owner"); await p.fill("[name=email]", "owner@example.com"); await p.fill("[name=password]", "motdepasse-solide-1");
  await p.click("button:has-text(\"S'inscrire\")"); await p.waitForURL("**/dashboard");
  const tok = (await (await fetch(API + "/auth/login", { method: "POST", body: new URLSearchParams({ username: "owner@example.com", password: "motdepasse-solide-1" }) })).json()).access_token;
  const H = { Authorization: "Bearer " + tok };
  const fd = new FormData(); fd.append("file", new Blob([require("fs").readFileSync("/tmp/synth.csv")]), "s.csv");
  await fetch(API + "/import/matches", { method: "POST", headers: H, body: fd });
  const teams = Object.fromEntries((await (await fetch(API + "/teams?limit=500")).json()).map((t) => [t.name, t.id]));
  const comp = (await (await fetch(API + "/competitions")).json())[0].id;
  for (const [d, [a, c]] of [[1, [1, 2]], [2, [3, 4]], [3, [5, 6]], [4, [7, 8]]])
    await fetch(API + "/matches", { method: "POST", headers: { ...H, "content-type": "application/json" }, body: JSON.stringify({ competition_id: comp, home_team_id: teams["Equipe " + a], away_team_id: teams["Equipe " + c], kickoff_at: new Date(Date.now() + d * 86400e3).toISOString() }) });
  await p.goto("http://localhost:3000/assistant"); await p.waitForSelector("text=Mode règles");
  console.log("1 statut : mode règles affiché, aucun LLM prétendu OK");
  await p.fill("[aria-label='Votre message']", "Analyse Equipe 1 contre Equipe 2"); await p.click("button:has-text('Envoyer')");
  await p.waitForSelector("text=/Modèle poisson v1\\.\\d+\\.\\d+/"); await p.waitForSelector("text=Limites :"); console.log("2 analyse de match via l'assistant OK");
  await p.fill("[aria-label='Votre message']", "Analyse Arsenal contre Chelsea"); await p.click("button:has-text('Envoyer')");
  await p.waitForSelector("text=pas identifié d'équipe connue"); console.log("3 équipe inconnue : refus honnête OK");
  await p.fill("[aria-label='Votre message']", "Construis un combiné de trois rencontres en privilégiant les probabilités élevées"); await p.click("button:has-text('Envoyer')");
  await p.waitForSelector("text=Combiné de 3 sélections"); console.log("4 combiné via l'assistant OK");
  await p.goto("http://localhost:3000/combos"); await p.waitForSelector("text=Ajouter une sélection");
  await p.click("button:has-text('Proposer un combiné')"); await p.waitForSelector("text=Probabilité conjointe"); await p.waitForSelector("text=Hypothèse : les matchs différents");
  console.log("5 page combinés : suggestion + analyse + avertissements OK");
  await p.click("button:has-text('Analyser le combiné')"); await p.waitForSelector("text=Produit naïf");
  await b.close();
})().catch(async (e) => { try { console.error("BODY", (await global.P.innerText("body")).slice(0, 500).replace(/\n+/g, " | ")); } catch {} console.error("ÉCHEC", e.message.split("\n")[0]); process.exit(1); });
