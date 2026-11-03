// E2E historique/performance. Prérequis : base VIDE migrée, API :8000, frontend :3000, et /tmp/synth.csv
// (ligue SYNTHÉTIQUE générée par les tests : cd backend && python -c "from tests.synth import league ..."). Nettoyage des ports : fuser -k 3000/tcp 8000/tcp
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
  const kick = new Date(Date.now() + 86400e3).toISOString();
  const m = await (await fetch(API + "/matches", { method: "POST", headers: { ...H, "content-type": "application/json" },
    body: JSON.stringify({ competition_id: comp, home_team_id: teams["Equipe 1"], away_team_id: teams["Equipe 2"], kickoff_at: kick }) })).json();
  await p.goto("http://localhost:3000/performance"); await p.waitForSelector("text=Aucun événement réglé"); console.log("1 performance vide honnête OK");
  await p.goto(`http://localhost:3000/matches/${m.id}`); await p.waitForSelector("text=Buts attendus");
  await p.click("button:has-text('Enregistrer cette prédiction')"); await p.waitForSelector("text=immuable"); console.log("2 prédiction enregistrée OK");
  await p.selectOption("[name=status]", "finished"); await p.fill("[name=h]", "3"); await p.fill("[name=a]", "0"); await p.click("button:has-text('Enregistrer')");
  await p.goto("http://localhost:3000/history"); await p.waitForSelector("text=Gagné"); await p.waitForSelector("text=Perdu");
  console.log("3 historique + règlement automatique OK");
  await p.goto("http://localhost:3000/performance"); await p.waitForSelector("text=Seulement 3 événement(s)"); await p.waitForSelector("text=Par type de marché");
  console.log("4 performance : avertissement d'échantillon + ventilation OK");
  const r = await fetch(`${API}/matches/${m.id}/predictions`, { method: "POST", headers: H });
  console.log("5 ré-enregistrement :", (await r.json()).already_recorded === true ? "refusé/idempotent OK" : "ÉCHEC");
  await b.close();
})().catch(async (e) => { try { console.error("BODY", (await global.P.innerText("body")).slice(0, 400).replace(/\n+/g, " | ")); } catch {} console.error("ÉCHEC", e.message.split("\n")[0]); process.exit(1); });
