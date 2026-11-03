"use client";

import Link from "next/link";
import { useApi } from "@/lib/hooks";
import { Empty, PageTitle } from "@/components/ui";
import { SkeletonList, ago } from "@/components/kit";

export type League = { id: number; name: string; country: string | null; seasons: { id: number; season: string | null; matches: number; finished: number; upcoming: number }[]; matches: number; upcoming: number; last_result_at: string | null };

export default function Leagues() {
  const { data, loading, error } = useApi<League[]>("/leagues");
  return (
    <>
      <PageTitle title="Championnats" subtitle="Tous les championnats enregistrés, avec classements et résultats." />
      {error && <Empty>{error}</Empty>}
      {loading ? <SkeletonList /> : !data?.length ? (
        <Empty>Aucun championnat pour l&apos;instant. Un administrateur peut en ajouter en un clic depuis <Link className="text-accent underline" href="/data">Centre de données</Link>.</Empty>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.map((l) => (
            <Link key={l.id} href={`/leagues/${l.id}`} className="card hover:border-accent">
              <p className="font-medium">{l.name}</p>
              <p className="mt-1 text-xs text-muted">{l.seasons.length} saison(s) · {l.matches} matchs · dernier résultat {ago(l.last_result_at)}</p>
              {l.upcoming > 0 && <p className="mt-2"><span className="badge border-accent/50 text-accent">{l.upcoming} à venir</span></p>}
            </Link>))}
        </div>)}
    </>
  );
}
