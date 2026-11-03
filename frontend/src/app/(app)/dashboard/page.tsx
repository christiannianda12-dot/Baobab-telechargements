"use client";

import Link from "next/link";
import { useState } from "react";
import { useApi, dayStart } from "@/lib/hooks";
import { Empty, ErrorBox, PageTitle } from "@/components/ui";
import { Alert, SkeletonList, StatCard, ago } from "@/components/kit";
import MatchLine, { type MatchItem } from "@/components/MatchLine";
import type { League } from "../leagues/page";
import type { User } from "@/lib/api";

type Page = { total: number; items: MatchItem[] };

export default function Dashboard() {
  const [now] = useState(() => Date.now());
  const me = useApi<User>("/auth/me");
  const leagues = useApi<League[]>("/leagues");
  const upcoming = useApi<Page>(`/matches-search?status=scheduled&date_from=${encodeURIComponent(dayStart(0))}&order=asc&limit=8`);
  const recent = useApi<Page>("/matches-search?status=finished&order=desc&limit=6");
  const perf = useApi<{ overall: { settled: number; reliable: boolean; hit_rate?: number }; pending_predictions: number }>("/performance");
  const ls = leagues.data ?? [];
  const totalMatches = ls.reduce((n, l) => n + l.matches, 0);
  const last = ls.map((l) => l.last_result_at).filter(Boolean).sort().at(-1) ?? null;
  const staleDays = last ? Math.floor((now - new Date(last).getTime()) / 86400000) : null;
  const admin = me.data?.role === "admin";
  const err = leagues.error ?? upcoming.error ?? recent.error;

  return (
    <>
      <PageTitle title="Tableau de bord" subtitle={`Bonjour${me.data ? ` ${me.data.display_name.split(" ")[0]}` : ""} — vue d'ensemble de vos données.`} />
      {err && <ErrorBox message={err} />}
      {!leagues.loading && ls.length === 0 && (
        <Alert kind="info"><b>Commencez ici :</b> aucun championnat n&apos;est enregistré. {admin ? <>Ajoutez-en en un clic dans le <Link className="text-accent underline" href="/data">Centre de données</Link>.</> : "Demandez à un administrateur d'ajouter des championnats."}</Alert>)}
      {staleDays !== null && staleDays > 7 && (upcoming.data?.total ?? 0) > 0 && (
        <Alert kind="warn">Le dernier résultat enregistré date de {staleDays} jours alors que des matchs sont à venir. {admin ? <Link className="text-accent underline" href="/data">Mettre à jour les données</Link> : "Demandez une mise à jour des données."}</Alert>)}

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Championnats" value={leagues.loading ? "…" : ls.length} />
        <StatCard label="Matchs en base" value={leagues.loading ? "…" : totalMatches.toLocaleString("fr-FR")} />
        <StatCard label="Matchs à venir" value={upcoming.loading ? "…" : upcoming.data?.total ?? 0} />
        <StatCard label="Dernier résultat" value={leagues.loading ? "…" : ago(last)} tone={staleDays !== null && staleDays > 7 ? "warn" : undefined} />
      </div>

      <section className="mb-6">
        <div className="mb-2 flex items-baseline justify-between"><h2 className="text-lg font-medium">Prochains matchs</h2><Link href="/matches" className="text-sm text-accent">Tout voir</Link></div>
        {upcoming.loading ? <SkeletonList rows={3} /> : !upcoming.data?.items.length ? <Empty>Aucun match à venir enregistré.{admin && <> Utilisez « Tout mettre à jour » dans le <Link className="text-accent underline" href="/data">Centre de données</Link> pour récupérer le calendrier et les cotes.</>}</Empty>
          : <ul className="space-y-2">{upcoming.data.items.map((m) => <MatchLine key={m.id} m={m} />)}</ul>}
      </section>

      <section className="mb-6">
        <div className="mb-2 flex items-baseline justify-between"><h2 className="text-lg font-medium">Derniers résultats</h2><Link href="/matches" className="text-sm text-accent">Tout voir</Link></div>
        {recent.loading ? <SkeletonList rows={3} /> : !recent.data?.items.length ? <Empty>Aucun résultat enregistré.</Empty> : <ul className="space-y-2">{recent.data.items.map((m) => <MatchLine key={m.id} m={m} />)}</ul>}
      </section>

      <div className="grid gap-3 sm:grid-cols-2">
        <Link href="/reliability" className="card hover:border-accent"><h2 className="font-medium">Fiabilité du modèle</h2><p className="mt-2 text-sm text-muted">Le modèle est comparé en permanence au marché des bookmakers sur l&apos;historique. À lire avant de s&apos;en servir.</p></Link>
        <Link href="/performance" className="card hover:border-accent"><h2 className="font-medium">Performances de l&apos;IA</h2>
          {!perf.data || perf.data.overall.settled === 0 ? <p className="mt-2 text-sm text-muted">Aucun événement réglé{perf.data ? ` (${perf.data.pending_predictions} prédiction(s) en attente)` : ""}.</p> :
            <p className="mt-2 text-sm">{perf.data.overall.settled} événement(s) réglé(s), réussite {((perf.data.overall.hit_rate ?? 0) * 100).toFixed(1)} %.{!perf.data.overall.reliable && <span className="text-yellow-300"> Échantillon trop petit pour conclure.</span>}</p>}</Link>
      </div>
    </>
  );
}
