"use client";

import { useApi, dayStart } from "@/lib/hooks";
import type { Match } from "@/lib/api";
import { Empty, ErrorBox, Loading, MatchList, PageTitle, useCatalog } from "@/components/ui";

export default function MatchesToday() {
  const cat = useCatalog();
  const { data, error, loading } = useApi<Match[]>(`/matches?date_from=${encodeURIComponent(dayStart(0))}&date_to=${encodeURIComponent(dayStart(1))}`);
  return (
    <>
      <PageTitle title="Matchs du jour" subtitle={new Date().toLocaleDateString("fr-FR", { dateStyle: "full" })} />
      {error && <ErrorBox message={error} />}
      {loading ? <Loading what="matchs" /> : data?.length ? <MatchList matches={data} cat={cat} /> : <Empty>Aucun match enregistré aujourd&apos;hui.</Empty>}
    </>
  );
}
