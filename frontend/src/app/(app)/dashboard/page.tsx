"use client";

import Link from "next/link";
import { useApi, dayStart } from "@/lib/hooks";
import type { Match } from "@/lib/api";
import { Empty, ErrorBox, Loading, MatchList, PageTitle, useCatalog } from "@/components/ui";

export default function Dashboard() {
  const cat = useCatalog();
  const today = useApi<Match[]>(`/matches?date_from=${encodeURIComponent(dayStart(0))}&date_to=${encodeURIComponent(dayStart(1))}`);
  const tomorrow = useApi<Match[]>(`/matches?date_from=${encodeURIComponent(dayStart(1))}&date_to=${encodeURIComponent(dayStart(2))}`);
  const err = today.error ?? tomorrow.error ?? cat.error;

  return (
    <>
      <PageTitle title="Tableau de bord" subtitle="Vue d'ensemble des données enregistrées." />
      {err && <ErrorBox message={err} />}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Matchs aujourd'hui" value={today.data?.length} />
        <Stat label="Matchs demain" value={tomorrow.data?.length} />
        <Stat label="Compétitions" value={cat.comps?.length} />
        <Stat label="Équipes" value={cat.teams?.length} />
      </div>
      <Section title="Aujourd'hui" href="/matches">
        {today.loading ? <Loading what="matchs" /> : today.data?.length ? <MatchList matches={today.data} cat={cat} />
          : <Empty>Aucun match enregistré aujourd&apos;hui. Ajoutez-en depuis <Link className="text-accent" href="/admin">Administration</Link>.</Empty>}
      </Section>
      <Section title="Demain">
        {tomorrow.loading ? <Loading what="matchs" /> : tomorrow.data?.length ? <MatchList matches={tomorrow.data} cat={cat} />
          : <Empty>Aucun match enregistré demain.</Empty>}
      </Section>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="card"><h2 className="font-medium">Dernières analyses</h2>
          <p className="mt-2 text-sm text-muted">Aucune analyse : le moteur prédictif n&apos;est pas encore construit (étape 5).</p></div>
        <div className="card"><h2 className="font-medium">Performances de l&apos;IA</h2>
          <p className="mt-2 text-sm text-muted">Aucune prédiction enregistrée, donc aucune statistique de performance (étape 7).</p></div>
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value?: number }) {
  return <div className="card"><p className="text-2xl font-semibold">{value ?? "…"}</p><p className="text-xs text-muted">{label}</p></div>;
}

function Section({ title, href, children }: { title: string; href?: string; children: React.ReactNode }) {
  return (
    <section className="mb-6">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-lg font-medium">{title}</h2>
        {href && <Link href={href} className="text-sm text-accent">Tout voir</Link>}
      </div>
      {children}
    </section>
  );
}
