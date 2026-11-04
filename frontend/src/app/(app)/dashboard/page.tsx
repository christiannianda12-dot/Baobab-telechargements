"use client";

import Link from "next/link";
import { useState } from "react";
import { useApi } from "@/lib/hooks";
import { Empty, ErrorBox, PageTitle } from "@/components/ui";
import { Alert, Hint, ProbBar, SkeletonList, StatCard, ago, fmtDateTime } from "@/components/kit";
import MatchLine, { type MatchItem } from "@/components/MatchLine";
import type { League } from "../leagues/page";
import type { User } from "@/lib/api";

type Today = { id: number; kickoff_at: string; league: string | null; home: string; away: string; probabilities: { home: number; draw: number; away: number } | null;
  model_unavailable: string | null; best_odds: Record<string, { price: number; bookmaker: string }>; value_selections: string[]; recorded: boolean };

export default function Dashboard() {
  const [now] = useState(() => Date.now());
  const me = useApi<User>("/auth/me");
  const leagues = useApi<League[]>("/leagues", { refreshMs: 120000 });
  const today = useApi<Today[]>("/today?days=3&limit=12", { refreshMs: 60000 });
  const recent = useApi<{ total: number; items: MatchItem[] }>("/matches-search?status=finished&order=desc&limit=6", { refreshMs: 120000 });
  const perf = useApi<{ overall: { settled: number; reliable: boolean; hit_rate?: number }; pending_predictions: number }>("/performance", { refreshMs: 120000 });
  const ls = leagues.data ?? [];
  const totalMatches = ls.reduce((n, l) => n + l.matches, 0);
  const upcomingTotal = ls.reduce((n, l) => n + l.upcoming, 0);
  const last = ls.map((l) => l.last_result_at).filter(Boolean).sort().at(-1) ?? null;
  const staleDays = last ? Math.floor((now - new Date(last).getTime()) / 86400000) : null;
  const admin = me.data?.role === "admin";
  const err = leagues.error ?? today.error ?? recent.error;
  const valueCount = (today.data ?? []).filter((m) => m.value_selections.length).length;

  return (
    <>
      <PageTitle title="Tableau de bord" subtitle={`Bonjour${me.data ? ` ${me.data.display_name.split(" ")[0]}` : ""} — cette page se met à jour toute seule.`} />
      {err && <ErrorBox message={err} />}
      {!leagues.loading && ls.length === 0 && (
        <Alert kind="info"><b>Commencez ici :</b> aucun championnat n&apos;est enregistré. {admin ? <>Ajoutez-en en un clic dans le <Link className="text-accent underline" href="/data">Centre de données</Link> (championnats et coupes européennes).</> : "Demandez à un administrateur d'ajouter des championnats."}</Alert>)}
      {staleDays !== null && staleDays > 7 && upcomingTotal > 0 && (
        <Alert kind="warn">Le dernier résultat date de {staleDays} jours alors que des matchs sont à venir. La mise à jour automatique est-elle active ? <Link className="text-accent underline" href="/settings">Vérifier</Link></Alert>)}

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Championnats et coupes" value={leagues.loading ? "…" : ls.length} />
        <StatCard label="Matchs en base" value={leagues.loading ? "…" : totalMatches.toLocaleString("fr-FR")} />
        <StatCard label="Matchs à venir" value={leagues.loading ? "…" : upcomingTotal} />
        <StatCard label="Dernier résultat" value={leagues.loading ? "…" : ago(last)} tone={staleDays !== null && staleDays > 7 ? "warn" : undefined} />
      </div>

      <section className="mb-6">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-medium">Prochains matchs, analysés<Hint>Pour chaque match : la probabilité du modèle (victoire domicile / nul / victoire extérieur) et la meilleure cote trouvée entre bookmakers. « Valeur » = la cote paraît plus élevée que ce que le modèle estime.</Hint></h2>
          <span className="flex gap-3 text-sm"><Link href="/combos" className="text-accent">Combinés proposés →</Link><Link href="/matches" className="text-accent">Tous les matchs</Link></span>
        </div>
        {valueCount > 0 && <p className="mb-2 text-xs text-muted">{valueCount} match(s) avec une cote qui semble supérieure à l&apos;estimation. Rappel : le marché est globalement plus précis que le modèle (page Fiabilité).</p>}
        {today.loading ? <SkeletonList rows={3} /> : !today.data?.length ? <Empty>Aucun match à venir dans les 3 prochains jours.{admin && <> Lancez « Mettre à jour maintenant » (barre du haut) pour récupérer le calendrier et les cotes.</>}</Empty> : (
          <ul className="space-y-2">{today.data.map((m) => (
            <li key={m.id}>
              <Link href={`/matches/${m.id}`} className="card block hover:border-accent">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0"><p className="truncate font-medium">{m.home} <span className="text-muted">vs</span> {m.away}</p><p className="text-xs text-muted">{m.league} · {fmtDateTime(m.kickoff_at)}</p></div>
                  <div className="flex gap-1">{m.value_selections.length > 0 && <span className="badge border-accent/50 text-accent">Valeur</span>}{m.recorded && <span className="badge">Prédiction enregistrée</span>}</div>
                </div>
                <div className="mt-2 grid items-end gap-3 sm:grid-cols-[1fr_auto]">
                  {m.probabilities ? <ProbBar p={m.probabilities} labels={[m.home, m.away]} /> : <p className="text-xs text-muted">Pas de probabilité : {m.model_unavailable ?? "historique insuffisant"}</p>}
                  {Object.keys(m.best_odds).length > 0 && (
                    <div className="flex gap-1.5 text-xs" title="Meilleure cote trouvée entre bookmakers">{(["home", "draw", "away"] as const).map((s) => m.best_odds[s] && (
                      <span key={s} className={`rounded border px-1.5 py-0.5 ${m.value_selections.includes(s) ? "border-accent text-accent" : "border-border text-muted"}`}>{s === "home" ? "1" : s === "draw" ? "N" : "2"} <b>{m.best_odds[s].price.toFixed(2)}</b></span>))}</div>)}
                </div>
              </Link>
            </li>))}</ul>)}
      </section>

      <section className="mb-6">
        <div className="mb-2 flex items-baseline justify-between"><h2 className="text-lg font-medium">Derniers résultats</h2><Link href="/matches" className="text-sm text-accent">Tout voir</Link></div>
        {recent.loading ? <SkeletonList rows={3} /> : !recent.data?.items.length ? <Empty>Aucun résultat enregistré.</Empty> : <ul className="space-y-2">{recent.data.items.map((m) => <MatchLine key={m.id} m={m} />)}</ul>}
      </section>

      <div className="grid gap-3 sm:grid-cols-2">
        <Link href="/reliability" className="card hover:border-accent"><h2 className="font-medium">Fiabilité du modèle</h2><p className="mt-2 text-sm text-muted">Comparé en permanence au marché des bookmakers. À lire avant de s&apos;en servir.</p></Link>
        <Link href="/performance" className="card hover:border-accent"><h2 className="font-medium">Performances de l&apos;IA</h2>
          {!perf.data || perf.data.overall.settled === 0 ? <p className="mt-2 text-sm text-muted">Aucun événement réglé{perf.data ? ` (${perf.data.pending_predictions} prédiction(s) en attente)` : ""}.</p> :
            <p className="mt-2 text-sm">{perf.data.overall.settled} événement(s) réglé(s), réussite {((perf.data.overall.hit_rate ?? 0) * 100).toFixed(1)} %.{!perf.data.overall.reliable && <span className="text-yellow-300"> Échantillon trop petit pour conclure.</span>}</p>}</Link>
      </div>
    </>
  );
}
