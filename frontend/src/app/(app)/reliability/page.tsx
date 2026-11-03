"use client";

import { useState } from "react";
import { useApi } from "@/lib/hooks";
import { Empty, ErrorBox, Loading, PageTitle, useCatalog } from "@/components/ui";
import { CalibrationChart, LineChart } from "@/components/kit";

type Row = { brier: number; log_loss: number };
type Bin = { mean_predicted: number; observed_frequency: number; n: number };
type Paired = { mean: number; se: number; z: number };
type Bench = {
  available: boolean; reason?: string; matches?: number; reliable?: boolean; model: string; history_matches: number;
  scores?: Record<"model" | "market" | "baseline" | "chance", Row>;
  model_minus_market?: { brier: Paired; log_loss: Paired };
  by_season?: { season: string; matches: number; model_brier: number; market_brier: number; baseline_brier: number }[];
  value_bets?: { min_expected_value: number; bets: number; wins: number; profit_units: number; roi: number | null }[];
  verdict?: string; notes?: string[];
  calibration?: { model: Bin[]; market: Bin[] }; cumulative?: { date: string; brier_gap: number; profit: number }[];
};
const n4 = (x: number) => x.toFixed(4);
const pc = (x: number | null) => (x == null ? "—" : `${(x * 100).toFixed(1)} %`);
const LABELS: [keyof NonNullable<Bench["scores"]>, string][] = [
  ["chance", "Hasard pur (1/3 chacun)"], ["baseline", "Fréquences passées"], ["model", "Notre modèle"], ["market", "Marché (cotes de clôture)"],
];

export default function Reliability() {
  const cat = useCatalog();
  const leagues = [...new Map((cat.comps ?? []).map((c) => [c.name.trim().toLowerCase(), c])).values()];
  const [pick, setPick] = useState<string>("");
  const comp = pick || (leagues[0] ? String(leagues[0].id) : "");
  const { data, error, loading } = useApi<Bench>(comp ? `/benchmark/${comp}` : null);

  return (
    <>
      <PageTitle title="Fiabilité du modèle" subtitle="Notre modèle comparé au marché des bookmakers, sur les mêmes matchs passés. Plus l'erreur est basse, meilleur est le score." />
      {leagues.length > 1 && (
        <select className="input mb-4 max-w-xs" aria-label="Championnat" value={comp} onChange={(e) => setPick(e.target.value)}>
          {leagues.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>)}
      {error && <ErrorBox message={error} />}
      {!comp ? <Empty>Aucun championnat enregistré. Importez un historique (Administration).</Empty> : loading || !data ? <Loading what="calculs" /> : !data.available ? (
        <Empty>{data.reason}</Empty>
      ) : (<>
        <p className={`mb-4 rounded-lg border p-3 text-sm ${data.model_minus_market!.brier.z > 2 ? "border-yellow-500/40 bg-yellow-500/10 text-yellow-100" : "border-border bg-surface"}`}>
          <b>Verdict :</b> {data.verdict} <span className="text-muted">({data.matches} matchs comparés{data.reliable ? "" : " — échantillon court"})</span></p>

        <section className="card mb-4 overflow-x-auto"><h2 className="mb-2 font-medium">Erreur des probabilités (1X2)</h2>
          <table className="w-full min-w-[22rem] text-sm"><thead><tr className="text-left text-muted"><th></th><th>Brier</th><th>Log Loss</th></tr></thead>
            <tbody>{LABELS.map(([k, label]) => (
              <tr key={k} className={`border-t border-border ${k === "model" ? "font-medium text-accent" : ""}`}><td className="py-1">{label}</td><td>{n4(data.scores![k].brier)}</td><td>{n4(data.scores![k].log_loss)}</td></tr>))}</tbody></table>
          <p className="mt-2 text-xs text-muted">Écart modèle − marché : Brier {data.model_minus_market!.brier.mean >= 0 ? "+" : ""}{n4(data.model_minus_market!.brier.mean)} ± {n4(data.model_minus_market!.brier.se)} par match
            (z = {data.model_minus_market!.brier.z.toFixed(1)}). Un écart positif signifie que le modèle est moins précis ; |z| &gt; 2 : écart établi statistiquement.</p></section>

        <section className="card mb-4 overflow-x-auto"><h2 className="mb-2 font-medium">Saison par saison (Brier)</h2>
          <table className="w-full min-w-[26rem] text-sm"><thead><tr className="text-left text-muted"><th>Saison</th><th>Matchs</th><th>Modèle</th><th>Marché</th><th>Fréquences</th></tr></thead>
            <tbody>{data.by_season!.map((s) => (<tr key={s.season} className="border-t border-border"><td className="py-1">{s.season}</td><td>{s.matches}</td><td>{n4(s.model_brier)}</td><td>{n4(s.market_brier)}</td><td>{n4(s.baseline_brier)}</td></tr>))}</tbody></table></section>

        <section className="card mb-4 overflow-x-auto"><h2 className="mb-1 font-medium">Et si on avait parié sur les écarts du modèle ?</h2>
          <p className="mb-2 text-xs text-muted">Simulation rétrospective : 1 unité sur chaque issue dont la valeur espérée dépasse le seuil, aux cotes de clôture (marge incluse).</p>
          <table className="w-full min-w-[26rem] text-sm"><thead><tr className="text-left text-muted"><th>Seuil de valeur</th><th>Paris</th><th>Gagnés</th><th>Bilan</th><th>Rendement</th></tr></thead>
            <tbody>{data.value_bets!.map((v) => (<tr key={v.min_expected_value} className="border-t border-border"><td className="py-1">&gt; {(v.min_expected_value * 100).toFixed(0)} %</td><td>{v.bets}</td><td>{v.wins}</td>
              <td className={v.profit_units < 0 ? "text-red-300" : "text-accent"}>{v.profit_units.toFixed(1)}</td><td className={(v.roi ?? 0) < 0 ? "text-red-300" : "text-accent"}>{pc(v.roi)}</td></tr>))}</tbody></table></section>

        {data.calibration && data.cumulative && (
          <div className="mb-4 grid gap-4 md:grid-cols-2">
            <section className="card"><h2 className="mb-1 font-medium">Calibration (victoire à domicile)</h2><p className="mb-2 text-xs text-muted">Quand le modèle annonce 60 %, l&apos;événement arrive-t-il 60 % du temps ? Plus la courbe colle à la diagonale, mieux c&apos;est.</p>
              <CalibrationChart model={data.calibration.model} market={data.calibration.market} /></section>
            <section className="card"><h2 className="mb-1 font-medium">Écart cumulé au marché</h2><p className="mb-2 text-xs text-muted">Somme des différences de Brier (modèle − marché) : une courbe qui monte = le modèle perd du terrain sur le marché.</p>
              <LineChart xLabels={[data.cumulative[0].date, data.cumulative.at(-1)!.date]} yFormat={(v) => v.toFixed(1)} series={[{ name: "Écart cumulé (Brier)", color: "#f59e0b", points: data.cumulative.map((c, i) => ({ x: i, y: c.brier_gap })) }]} /></section>
            <section className="card md:col-span-2"><h2 className="mb-1 font-medium">Bilan cumulé des paris simulés sur les écarts du modèle</h2><p className="mb-2 text-xs text-muted">En unités de mise, aux cotes de clôture. Une courbe qui descend = ces paris auraient perdu de l&apos;argent.</p>
              <LineChart xLabels={[data.cumulative[0].date, data.cumulative.at(-1)!.date]} yFormat={(v) => v.toFixed(0)} series={[{ name: "Bilan (unités)", color: "#ef4444", points: data.cumulative.map((c, i) => ({ x: i, y: c.profit })) }]} /></section>
          </div>)}

        <ul className="list-disc space-y-1 pl-5 text-xs text-muted">{data.notes?.map((t) => <li key={t}>{t}</li>)}
          <li>Modèle : {data.model}, entraîné sur {data.history_matches} matchs (toutes saisons du championnat, les plus récents pesant davantage).</li></ul>
      </>)}
    </>
  );
}
