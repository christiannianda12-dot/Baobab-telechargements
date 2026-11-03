"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { api, type Match } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { ErrorBox, Loading, PageTitle, SourceBadge, useCatalog } from "@/components/ui";

type Stat = Record<string, number | string | null> & { team_id: number };
type Market = {
  bookmaker: string; market: string; line: number | null; complete: boolean; margin: number | null;
  selections: Record<string, { price: number; implied_probability: number }>;
  fair_probabilities: Record<string, number> | null;
};

const STAT_ROWS: [string, string][] = [
  ["shots", "Tirs"], ["shots_on_target", "Tirs cadrés"], ["corners", "Corners"],
  ["possession_pct", "Possession (%)"], ["fouls", "Fautes"], ["yellow_cards", "Cartons jaunes"], ["red_cards", "Cartons rouges"],
];
const SELECTIONS: Record<string, string[]> = {
  "1X2": ["home", "draw", "away"], DC: ["1X", "12", "X2"], OU: ["over", "under"], BTTS: ["yes", "no"], CORNERS_OU: ["over", "under"],
};
type Form = { played: number; results: string[]; wins: number; draws: number; losses: number; goals_for: number; goals_against: number;
  avg_goals_for: number | null; avg_goals_against: number | null; reliable: boolean;
  averages: Record<string, { average: number | null; samples: number }> };
type Analysis = { home: { overall: Form; at_home: Form }; away: { overall: Form; away: Form }; warnings: string[];
  head_to_head: { played: number; team_a_wins: number; team_b_wins: number; draws: number; team_a_goals: number; team_b_goals: number } };
const pct = (x: number) => `${(x * 100).toFixed(1)} %`;

export default function MatchDetail() {
  const id = useParams<{ id: string }>().id;
  const cat = useCatalog();
  const match = useApi<Match>(`/matches/${id}`);
  const stats = useApi<Stat[]>(`/matches/${id}/statistics`);
  const odds = useApi<{ markets: Market[] }>(`/matches/${id}/odds/analysis`);
  const analysis = useApi<Analysis>(`/matches/${id}/analysis`);

  if (match.loading) return <Loading what="données du match" />;
  if (match.error || !match.data) return <ErrorBox message={match.error ?? "Match introuvable."} />;
  const m = match.data;
  const home = cat.team.get(m.home_team_id) ?? "?", away = cat.team.get(m.away_team_id) ?? "?";
  const sh = stats.data?.find((s) => s.team_id === m.home_team_id), sa = stats.data?.find((s) => s.team_id === m.away_team_id);

  return (
    <>
      <PageTitle title={`${home} – ${away}`}
        subtitle={`${cat.comp.get(m.competition_id) ?? ""} · ${new Date(m.kickoff_at).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" })}`} />
      <p className="mb-4 flex flex-wrap gap-2"><span className="badge">{m.status}</span><SourceBadge source={m.source} />
        {m.home_score !== null && <span className="badge">Score {m.home_score} – {m.away_score}</span>}</p>

      <section className="card mb-4">
        <h2 className="mb-2 font-medium">Prédiction</h2>
        <p className="text-sm text-muted">Aucun modèle disponible : le moteur statistique n&apos;est pas encore construit (étape 5). Aucune probabilité n&apos;est affichée.</p>
      </section>

      <section className="card mb-4">
        <h2 className="mb-2 font-medium">Forme et confrontations directes</h2>
        <p className="mb-2 text-xs text-muted">Calculées uniquement sur les matchs terminés enregistrés avant le coup d&apos;envoi.</p>
        {analysis.loading ? <Loading what="analyses" /> : analysis.data && (<>
          <FormTable rows={[
            [`${home} (tous)`, analysis.data.home.overall], [`${home} (domicile)`, analysis.data.home.at_home],
            [`${away} (tous)`, analysis.data.away.overall], [`${away} (extérieur)`, analysis.data.away.away]]} />
          <p className="mt-3 text-sm">Confrontations directes : {analysis.data.head_to_head.played === 0 ? "aucune enregistrée." :
            `${analysis.data.head_to_head.played} match(s) — ${home} ${analysis.data.head_to_head.team_a_wins} V, ${analysis.data.head_to_head.draws} N, ${away} ${analysis.data.head_to_head.team_b_wins} V (buts ${analysis.data.head_to_head.team_a_goals}–${analysis.data.head_to_head.team_b_goals}).`}</p>
          {analysis.data.warnings.map((w) => <p key={w} className="mt-1 text-xs text-yellow-300">⚠ {w}</p>)}
        </>)}
      </section>

      <section className="card mb-4">
        <h2 className="mb-2 font-medium">Statistiques du match</h2>
        {!sh && !sa ? <p className="text-sm text-muted">Aucune statistique enregistrée.</p> : (
          <table className="w-full text-sm"><thead><tr className="text-left text-muted"><th /><th>{home}</th><th>{away}</th></tr></thead>
            <tbody>{STAT_ROWS.map(([k, label]) => (
              <tr key={k} className="border-t border-border"><td className="py-1 text-muted">{label}</td><td>{sh?.[k] ?? "—"}</td><td>{sa?.[k] ?? "—"}</td></tr>))}</tbody></table>)}
        <p className="mt-2 text-xs text-muted">« — » = donnée non renseignée.</p>
      </section>

      <section className="card mb-4">
        <h2 className="mb-2 font-medium">Cotes saisies</h2>
        {odds.loading ? <Loading what="cotes" /> : !odds.data?.markets.length ? <p className="text-sm text-muted">Aucune cote saisie pour ce match.</p> :
          odds.data.markets.map((mk) => (
            <div key={`${mk.bookmaker}${mk.market}${mk.line}`} className="mb-3 text-sm">
              <p className="font-medium">{mk.bookmaker} · {mk.market}{mk.line !== null ? ` ${mk.line}` : ""}
                {mk.margin !== null && <span className="ml-2 font-normal text-muted">marge {pct(mk.margin)}</span>}</p>
              <table className="mt-1 w-full"><thead><tr className="text-left text-muted"><th>Issue</th><th>Cote</th><th>Implicite</th><th>Corrigée</th></tr></thead>
                <tbody>{Object.entries(mk.selections).map(([s, v]) => (
                  <tr key={s} className="border-t border-border"><td className="py-1">{s}</td><td>{v.price}</td><td>{pct(v.implied_probability)}</td>
                    <td>{mk.fair_probabilities ? pct(mk.fair_probabilities[s]) : "—"}</td></tr>))}</tbody></table>
              {!mk.complete && <p className="text-xs text-muted">Marché incomplet : correction de marge impossible.</p>}
            </div>))}
        <OddsForm matchId={m.id} onDone={odds.reload} />
      </section>

      <ResultForm match={m} onDone={match.reload} />
    </>
  );
}

function OddsForm({ matchId, onDone }: { matchId: number; onDone: () => void }) {
  const [market, setMarket] = useState("1X2");
  const [err, setErr] = useState<string | null>(null);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget, f = new FormData(form);
    const line = String(f.get("line") ?? "");
    setErr(null);
    try {
      await api(`/matches/${matchId}/odds`, { method: "POST", json: {
        bookmaker: String(f.get("bookmaker")), market, selection: String(f.get("selection")),
        price: Number(f.get("price")), line: line ? Number(line) : null } });
      form.reset(); onDone();
    } catch (x) { setErr((x as Error).message); }
  }
  return (
    <form onSubmit={submit} className="mt-3 grid grid-cols-2 gap-2 border-t border-border pt-3 sm:grid-cols-5">
      <input name="bookmaker" required placeholder="Bookmaker" defaultValue="Manuel" className="input" aria-label="Bookmaker" />
      <select value={market} onChange={(e) => setMarket(e.target.value)} className="input" aria-label="Marché">{Object.keys(SELECTIONS).map((k) => <option key={k}>{k}</option>)}</select>
      <select name="selection" className="input" aria-label="Issue" key={market}>{SELECTIONS[market].map((s) => <option key={s}>{s}</option>)}</select>
      {(market === "OU" || market === "CORNERS_OU") && <input name="line" type="number" step="0.5" required placeholder="Ligne" className="input" aria-label="Ligne" />}
      <input name="price" type="number" step="0.01" min="1.01" required placeholder="Cote" className="input" aria-label="Cote" />
      <button className="btn col-span-2 sm:col-span-1">Ajouter la cote</button>
      {err && <div className="col-span-full"><ErrorBox message={err} /></div>}
    </form>
  );
}

function ResultForm({ match, onDone }: { match: Match; onDone: () => void }) {
  const [err, setErr] = useState<string | null>(null);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const h = String(f.get("h")), a = String(f.get("a"));
    setErr(null);
    try {
      await api(`/matches/${match.id}`, { method: "PATCH", json: { status: String(f.get("status")), home_score: h === "" ? null : Number(h), away_score: a === "" ? null : Number(a) } });
      onDone();
    } catch (x) { setErr((x as Error).message); }
  }
  return (
    <form onSubmit={submit} className="card grid grid-cols-3 gap-2 sm:grid-cols-5">
      <h2 className="col-span-full font-medium">Mettre à jour le résultat</h2>
      <select name="status" defaultValue={match.status} className="input col-span-3 sm:col-span-2" aria-label="Statut">
        {["scheduled", "live", "finished", "postponed", "cancelled"].map((s) => <option key={s}>{s}</option>)}</select>
      <input name="h" type="number" min="0" defaultValue={match.home_score ?? ""} placeholder="Dom." className="input" aria-label="Score domicile" />
      <input name="a" type="number" min="0" defaultValue={match.away_score ?? ""} placeholder="Ext." className="input" aria-label="Score extérieur" />
      <button className="btn">Enregistrer</button>
      {err && <div className="col-span-full"><ErrorBox message={err} /></div>}
    </form>
  );
}

const AVG: [string, string][] = [["corners", "Corners"], ["shots", "Tirs"], ["possession_pct", "Poss. %"], ["yellow_cards", "Jaunes"]];

function FormTable({ rows }: { rows: [string, Form][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] text-sm">
        <thead><tr className="text-left text-muted"><th>Équipe</th><th>J</th><th>V-N-D</th><th>Buts</th><th>Moy. +/-</th><th>Série</th>{AVG.map(([, l]) => <th key={l}>{l}</th>)}</tr></thead>
        <tbody>{rows.map(([label, f]) => (
          <tr key={label} className="border-t border-border">
            <td className="py-1 pr-2">{label}</td><td>{f.played}</td><td>{f.wins}-{f.draws}-{f.losses}</td><td>{f.goals_for}:{f.goals_against}</td>
            <td>{f.avg_goals_for ?? "—"} / {f.avg_goals_against ?? "—"}</td><td className="font-mono">{f.results.join("") || "—"}</td>
            {AVG.map(([k]) => { const a = f.averages[k]; return <td key={k} title={`${a.samples} match(s) avec donnée`}>{a.average ?? "—"}{a.samples > 0 && a.samples < f.played ? <sup className="text-muted"> {a.samples}/{f.played}</sup> : null}</td>; })}
          </tr>))}</tbody>
      </table>
    </div>
  );
}
