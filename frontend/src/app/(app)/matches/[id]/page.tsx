"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Tabs, useConfirm, useToast } from "@/components/kit";
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
  const pred = useApi<Prediction>(`/matches/${id}/prediction`);
  const recorded = useApi<{ id: number; created_at: string; outcome: string | null }[]>(`/predictions?match_id=${id}`);

  const [tab, setTab] = useState<"pred" | "form" | "odds" | "stats" | "result">("pred");

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
        {m.home_score !== null && <span className="badge">Score {m.home_score} – {m.away_score}</span>}
        <Link className="text-sm text-accent underline" href={`/teams/${m.home_team_id}`}>Fiche {home}</Link>
        <Link className="text-sm text-accent underline" href={`/teams/${m.away_team_id}`}>Fiche {away}</Link></p>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "pred", label: "Prédiction" }, { id: "form", label: "Forme" }, { id: "odds", label: "Cotes", badge: odds.data?.markets.length || undefined }, { id: "stats", label: "Statistiques" }, { id: "result", label: "Résultat" }]} />

      {tab === "pred" && (<>
      <PredictionCard p={pred.data} loading={pred.loading} home={home} away={away} />
      <RecordBox matchId={m.id} kickoff={m.kickoff_at} available={!!pred.data?.available} rows={recorded.data} onDone={recorded.reload} />
      </>)}
      {tab === "form" && (<>
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
      </>)}
      {tab === "stats" && (<>
      <section className="card mb-4">
        <h2 className="mb-2 font-medium">Statistiques du match</h2>
        {!sh && !sa ? <p className="text-sm text-muted">Aucune statistique enregistrée.</p> : (
          <table className="w-full text-sm"><thead><tr className="text-left text-muted"><th /><th>{home}</th><th>{away}</th></tr></thead>
            <tbody>{STAT_ROWS.map(([k, label]) => (
              <tr key={k} className="border-t border-border"><td className="py-1 text-muted">{label}</td><td>{sh?.[k] ?? "—"}</td><td>{sa?.[k] ?? "—"}</td></tr>))}</tbody></table>)}
        <p className="mt-2 text-xs text-muted">« — » = donnée non renseignée.</p>
      </section>
      </>)}
      {tab === "odds" && (<>
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
      </>)}
      {tab === "result" && (<>
      <ResultForm match={m} onDone={match.reload} />
      </>)}
    </>
  );
}

function OddsForm({ matchId, onDone }: { matchId: number; onDone: () => void }) {
  const [market, setMarket] = useState("1X2");
  const toast = useToast();
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
      form.reset(); toast("ok", "Cote ajoutée."); onDone();
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
  const toast = useToast();
  const confirm = useConfirm();
  const [err, setErr] = useState<string | null>(null);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const h = String(f.get("h")), a = String(f.get("a"));
    setErr(null);
    if (String(f.get("status")) === "finished" && h !== "" && a !== "" && !(await confirm({ title: `Enregistrer le résultat ${h} – ${a} ?`, message: "Les prédictions enregistrées pour ce match seront réglées automatiquement et ne pourront plus être modifiées.", confirmLabel: "Enregistrer le résultat" }))) return;
    try {
      await api(`/matches/${match.id}`, { method: "PATCH", json: { status: String(f.get("status")), home_score: h === "" ? null : Number(h), away_score: a === "" ? null : Number(a) } });
      toast("ok", "Résultat enregistré.");
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

type Prediction = {
  available: boolean; reason?: string; limitations: string[]; value_note?: string;
  model: { name: string; version: string }; training: { matches: number; home_team_matches: number; away_team_matches: number };
  expected_goals?: { home: number; away: number };
  probabilities?: { "1X2": Record<string, number>; DC: Record<string, number>; OU: Record<string, { over: number; under: number }>;
    BTTS: Record<string, number>; exact_scores: { score: string; probability: number }[] };
  value?: { bookmaker: string; market: string; selection: string; line: number | null; price: number; estimated_probability: number; edge: number; expected_value: number }[];
};

function Bar({ label, p }: { label: string; p: number }) {
  return (
    <div className="mb-1 text-sm"><div className="flex justify-between"><span>{label}</span><span className="font-mono">{pct(p)}</span></div>
      <div className="h-1.5 rounded bg-border"><div className="h-1.5 rounded bg-accent" style={{ width: `${p * 100}%` }} /></div></div>
  );
}

function PredictionCard({ p, loading, home, away }: { p?: Prediction; loading: boolean; home: string; away: string }) {
  return (
    <section className="card mb-4">
      <h2 className="mb-1 font-medium">Prédiction statistique</h2>
      {loading || !p ? <Loading what="calculs" /> : (<>
        <p className="mb-3 text-xs text-muted">Modèle {p.model.name} v{p.model.version} · {p.training.matches} match(s) d&apos;historique dans la compétition
          ({p.training.home_team_matches} pour {home}, {p.training.away_team_matches} pour {away}).</p>
        {!p.available || !p.probabilities ? <p className="text-sm text-yellow-300">Prédiction non produite : {p.reason}</p> : (<>
          <p className="mb-2 text-sm text-muted">Buts attendus : {home} {p.expected_goals!.home.toFixed(2)} – {p.expected_goals!.away.toFixed(2)} {away}</p>
          <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
            <div><Bar label={`Victoire ${home}`} p={p.probabilities["1X2"].home} /><Bar label="Match nul" p={p.probabilities["1X2"].draw} /><Bar label={`Victoire ${away}`} p={p.probabilities["1X2"].away} /></div>
            <div><Bar label="Plus de 2,5 buts" p={p.probabilities.OU["2.5"].over} /><Bar label="Moins de 2,5 buts" p={p.probabilities.OU["2.5"].under} />
              <Bar label="Les deux équipes marquent" p={p.probabilities.BTTS.yes} /></div>
          </div>
          <p className="mt-2 text-xs text-muted">Double chance : 1X {pct(p.probabilities.DC["1X"])} · 12 {pct(p.probabilities.DC["12"])} · X2 {pct(p.probabilities.DC["X2"])}.
            Scores les plus probables (indicatif) : {p.probabilities.exact_scores.slice(0, 3).map((x) => `${x.score} (${pct(x.probability)})`).join(", ")}.</p>
          {p.value && p.value.length > 0 && (
            <table className="mt-3 w-full text-sm"><thead><tr className="text-left text-muted"><th>Cote saisie</th><th>Cote</th><th>Proba modèle</th><th>Écart</th><th>Valeur espérée</th></tr></thead>
              <tbody>{p.value.map((v, i) => (<tr key={i} className="border-t border-border"><td className="py-1">{v.market} {v.selection}{v.line !== null ? ` ${v.line}` : ""}</td><td>{v.price}</td>
                <td>{pct(v.estimated_probability)}</td><td>{(v.edge * 100).toFixed(1)} pt</td><td className={v.expected_value > 0 ? "text-accent" : ""}>{(v.expected_value * 100).toFixed(1)} %</td></tr>))}</tbody></table>)}
          {p.value_note && p.value && p.value.length > 0 && <p className="mt-1 text-xs text-muted">{p.value_note} <a className="text-accent underline" href="/reliability">Voir la fiabilité mesurée</a>.</p>}
        </>)}
        <details className="mt-3 text-xs text-muted"><summary className="cursor-pointer">Limites du modèle</summary>
          <ul className="mt-1 list-disc pl-5">{p.limitations.map((l) => <li key={l}>{l}</li>)}</ul></details>
      </>)}
    </section>
  );
}

function RecordBox({ matchId, kickoff, available, rows, onDone }: { matchId: number; kickoff: string; available: boolean; rows?: { created_at: string; outcome: string | null }[]; onDone: () => void }) {
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (rows === undefined) return null;
  if (rows.length > 0) {
    const done = rows.filter((r) => r.outcome).length;
    return <p className="card mb-4 text-sm">Prédiction enregistrée le {new Date(rows[0].created_at).toLocaleString("fr-FR")} — <b>immuable</b>. {done === rows.length ? "Toutes réglées." : `${rows.length - done} issue(s) en attente de résultat.`}</p>;
  }
  if (!available || new Date(kickoff) <= new Date()) return <p className="card mb-4 text-xs text-muted">Enregistrement impossible : {new Date(kickoff) <= new Date() ? "le match a commencé." : "prédiction indisponible."}</p>;
  async function go() {
    setBusy(true); setErr(null);
    try { await api(`/matches/${matchId}/predictions`, { method: "POST" }); onDone(); } catch (e) { setErr((e as Error).message); }
    setBusy(false);
  }
  return (
    <div className="card mb-4">
      <button className="btn" disabled={busy} onClick={go}>Enregistrer cette prédiction</button>
      <p className="mt-2 text-xs text-muted">Horodatée et définitive : elle ne pourra plus être modifiée ni supprimée, et sera comparée au résultat réel.</p>
      {err && <ErrorBox message={err} />}
    </div>
  );
}
