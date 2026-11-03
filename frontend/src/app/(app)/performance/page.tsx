"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { Empty, ErrorBox, Loading, PageTitle, useCatalog } from "@/components/ui";

export type Summary = { settled: number; reliable: boolean; hit_rate?: number; hit_rate_ci95?: [number, number] | null; brier?: number; log_loss?: number;
  top_pick_bets?: { n: number; roi: number | null }; value_bets?: { n: number; roi: number | null } };
type Perf = { overall: Summary; voided: number; pending_predictions: number; by_market: Record<string, Summary>; by_competition: Record<string, Summary>; notes: string[] };

const pc = (x?: number | null) => (x == null ? "—" : `${(x * 100).toFixed(1)} %`);
const nb = (x?: number | null) => (x == null ? "—" : x.toFixed(3));

export default function Performance() {
  const { data, error, loading, reload } = useApi<Perf>("/performance");
  const cat = useCatalog();
  const [busy, setBusy] = useState(false);
  async function settle() { setBusy(true); try { await api("/predictions/settle", { method: "POST" }); reload(); } finally { setBusy(false); } }

  return (
    <>
      <PageTitle title="Statistiques de performance" subtitle="Calculées uniquement sur des prédictions enregistrées avant le match puis réglées." />
      {error && <ErrorBox message={error} />}
      {loading || !data ? <Loading what="statistiques" /> : data.overall.settled === 0 ? (
        <Empty>Aucun événement réglé pour l&apos;instant ({data.pending_predictions} prédiction(s) en attente, {data.voided} annulée(s)). Les statistiques apparaîtront après les premiers résultats.</Empty>
      ) : (<>
        {!data.overall.reliable && <p className="mb-3 rounded-lg border border-yellow-500/40 bg-yellow-500/10 p-3 text-sm text-yellow-200">
          Seulement {data.overall.settled} événement(s) réglé(s) : ces chiffres ne sont pas statistiquement fiables (seuil : 100).</p>}
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Événements réglés" value={String(data.overall.settled)} />
          <Kpi label="Taux de réussite" value={pc(data.overall.hit_rate)} hint={data.overall.hit_rate_ci95 ? `IC95 ${pc(data.overall.hit_rate_ci95[0])}–${pc(data.overall.hit_rate_ci95[1])}` : ""} />
          <Kpi label="ROI théorique (favori)" value={pc(data.overall.top_pick_bets?.roi)} hint={`${data.overall.top_pick_bets?.n ?? 0} pari(s) avec cote`} />
          <Kpi label="ROI value bets" value={pc(data.overall.value_bets?.roi)} hint={`${data.overall.value_bets?.n ?? 0} pari(s)`} />
        </div>
        <Table title="Par type de marché" rows={Object.entries(data.by_market)} />
        <Table title="Par championnat" rows={Object.entries(data.by_competition).map(([k, v]) => [cat.comp.get(Number(k)) ?? `Compétition ${k}`, v] as [string, Summary])} />
      </>)}
      <button className="btn-ghost mt-2" disabled={busy} onClick={settle}>Régler les matchs terminés</button>
      <ul className="mt-4 list-disc space-y-1 pl-5 text-xs text-muted">{data?.notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return <div className="card"><p className="text-xl font-semibold">{value}</p><p className="text-xs text-muted">{label}</p>{hint && <p className="text-[11px] text-muted">{hint}</p>}</div>;
}

function Table({ title, rows }: { title: string; rows: [string, Summary][] }) {
  return (
    <section className="card mb-4 overflow-x-auto"><h2 className="mb-2 font-medium">{title}</h2>
      <table className="w-full min-w-[30rem] text-sm"><thead><tr className="text-left text-muted"><th></th><th>Réglés</th><th>Réussite</th><th>Brier</th><th>Log Loss</th><th>ROI favori</th></tr></thead>
        <tbody>{rows.map(([k, s]) => (
          <tr key={k} className="border-t border-border"><td className="py-1">{k}{!s.reliable && <span className="badge ml-2">peu fiable</span>}</td>
            <td>{s.settled}</td><td>{pc(s.hit_rate)}</td><td>{nb(s.brier)}</td><td>{nb(s.log_loss)}</td><td>{pc(s.top_pick_bets?.roi)}</td></tr>))}</tbody></table>
    </section>
  );
}
