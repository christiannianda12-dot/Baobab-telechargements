"use client";

import { useState } from "react";
import { api, type Match } from "@/lib/api";
import { dayStart, useApi } from "@/lib/hooks";
import { Empty, ErrorBox, Loading, PageTitle, useCatalog } from "@/components/ui";

type Leg = { match_id: number; market: string; selection: string; line: number | null };
type Result = {
  valid: boolean; problems?: string[]; warnings?: string[]; joint_probability?: number; naive_product?: number; total_odds?: number | null; expected_value?: number | null;
  legs?: (Leg & { label: string; probability: number; odds: number | null })[]; skipped?: { match_id: number; reason: string }[]; selection_rule?: string;
};
const OPTIONS: [string, string, string, number | null][] = [
  ["1X2|home", "1X2", "home", null], ["1X2|draw", "1X2", "draw", null], ["1X2|away", "1X2", "away", null],
  ["DC|1X", "DC", "1X", null], ["DC|12", "DC", "12", null], ["DC|X2", "DC", "X2", null],
  ["OU|over|2.5", "OU", "over", 2.5], ["OU|under|2.5", "OU", "under", 2.5], ["OU|over|1.5", "OU", "over", 1.5], ["OU|under|3.5", "OU", "under", 3.5],
  ["BTTS|yes", "BTTS", "yes", null], ["BTTS|no", "BTTS", "no", null],
];
const LABEL: Record<string, string> = { home: "Victoire domicile", draw: "Nul", away: "Victoire extérieur", "1X": "Domicile ou nul", "12": "Domicile ou extérieur", X2: "Nul ou extérieur", over: "Plus de", under: "Moins de", yes: "Les 2 équipes marquent", no: "Pas les 2 équipes" };
const pc = (x?: number | null) => (x == null ? "—" : `${(x * 100).toFixed(1)} %`);

export default function Combos() {
  const cat = useCatalog();
  const upcoming = useApi<Match[]>(`/matches?date_from=${encodeURIComponent(dayStart(0))}&limit=200`);
  const [legs, setLegs] = useState<Leg[]>([]);
  const [matchId, setMatchId] = useState("");
  const [opt, setOpt] = useState(OPTIONS[0][0]);
  const [size, setSize] = useState(3);
  const [res, setRes] = useState<Result | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const mname = (id: number) => { const m = upcoming.data?.find((x) => x.id === id); return m ? `${cat.team.get(m.home_team_id) ?? "?"} – ${cat.team.get(m.away_team_id) ?? "?"}` : `Match ${id}`; };
  const legText = (l: Leg) => `${LABEL[l.selection]}${l.line !== null ? ` ${l.line}` : ""} (${l.market})`;

  async function call(path: string, json: object, after?: (r: Result) => void) {
    setBusy(true); setErr(null);
    try { const r = await api<Result>(path, { method: "POST", json }); setRes(r); after?.(r); } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }
  function add() {
    const o = OPTIONS.find((x) => x[0] === opt)!;
    if (!matchId) return;
    setLegs((l) => [...l, { match_id: Number(matchId), market: o[1], selection: o[2], line: o[3] }]); setRes(null);
  }

  return (
    <>
      <PageTitle title="Générateur de combinés" subtitle="Les sélections d'un même match sont corrélées : leur probabilité conjointe est calculée exactement, jamais par simple produit." />
      {upcoming.loading ? <Loading what="matchs" /> : !upcoming.data?.length ? <Empty>Aucun match à venir enregistré.</Empty> : (<>
        <section className="card mb-4">
          <h2 className="mb-2 font-medium">Ajouter une sélection</h2>
          <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
            <select className="input" aria-label="Match" value={matchId} onChange={(e) => setMatchId(e.target.value)}>
              <option value="">Match…</option>{upcoming.data.map((m) => <option key={m.id} value={m.id}>{mname(m.id)} — {new Date(m.kickoff_at).toLocaleDateString("fr-FR")}</option>)}</select>
            <select className="input" aria-label="Sélection" value={opt} onChange={(e) => setOpt(e.target.value)}>
              {OPTIONS.map(([k, , s, ln]) => <option key={k} value={k}>{LABEL[s]}{ln !== null ? ` ${ln}` : ""} ({k.split("|")[0]})</option>)}</select>
            <button className="btn" onClick={add} disabled={!matchId}>Ajouter</button>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3 text-sm">
            <span className="text-muted">ou laisser le moteur proposer</span>
            <select className="input w-auto" aria-label="Nombre de matchs" value={size} onChange={(e) => setSize(Number(e.target.value))}>{[2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select>
            <button className="btn-ghost" disabled={busy} onClick={() => call("/combos/suggest", { size }, (r) => r.valid && r.legs && setLegs(r.legs.map(({ match_id, market, selection, line }) => ({ match_id, market, selection, line }))))}>
              Proposer un combiné (probabilités élevées)</button>
          </div>
        </section>
        {legs.length > 0 && (
          <section className="card mb-4">
            <h2 className="mb-2 font-medium">Sélections ({legs.length})</h2>
            <ul className="divide-y divide-border text-sm">{legs.map((l, i) => (
              <li key={i} className="flex items-center justify-between gap-2 py-2"><span>{mname(l.match_id)} · {legText(l)}</span>
                <button className="btn-ghost" onClick={() => { setLegs(legs.filter((_, j) => j !== i)); setRes(null); }} aria-label="Retirer">✕</button></li>))}</ul>
            <button className="btn mt-3" disabled={busy} onClick={() => call("/combos/analyze", { legs })}>Analyser le combiné</button>
          </section>)}
      </>)}
      {err && <ErrorBox message={err} />}
      {res && !res.valid && <div className="card border-yellow-500/40 text-sm"><p className="font-medium text-yellow-300">Combiné non analysable</p>
        <ul className="mt-1 list-disc pl-5 text-muted">{res.problems?.map((p) => <li key={p}>{p}</li>)}</ul></div>}
      {res?.valid && res.legs && (
        <section className="card">
          <h2 className="mb-2 font-medium">Analyse</h2>
          <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
            <div><p className="text-xl font-semibold">{pc(res.joint_probability)}</p><p className="text-xs text-muted">Probabilité conjointe</p></div>
            <div><p className="text-xl font-semibold">{res.total_odds ? res.total_odds.toFixed(2) : "—"}</p><p className="text-xs text-muted">Cote totale (saisies)</p></div>
            <div><p className={`text-xl font-semibold ${res.expected_value != null && res.expected_value > 0 ? "text-accent" : ""}`}>{res.expected_value != null ? `${(res.expected_value * 100).toFixed(1)} %` : "—"}</p><p className="text-xs text-muted">Valeur espérée</p></div>
            <div><p className="text-xl font-semibold">{pc(res.naive_product)}</p><p className="text-xs text-muted">Produit naïf (comparaison)</p></div>
          </div>
          <table className="w-full text-sm"><thead><tr className="text-left text-muted"><th>Sélection</th><th>Proba</th><th>Cote saisie</th></tr></thead>
            <tbody>{res.legs.map((l, i) => <tr key={i} className="border-t border-border"><td className="py-1">{mname(l.match_id)} · {l.label}</td><td>{pc(l.probability)}</td><td>{l.odds ?? "—"}</td></tr>)}</tbody></table>
          {res.selection_rule && <p className="mt-2 text-xs text-muted">{res.selection_rule}</p>}
          <ul className="mt-3 space-y-1 text-xs text-yellow-200">{res.warnings?.map((w) => <li key={w}>⚠ {w}</li>)}</ul>
        </section>)}
    </>
  );
}
