"use client";

import { useState } from "react";
import { useApi, dayStart } from "@/lib/hooks";
import type { Match } from "@/lib/api";
import { Empty, ErrorBox, Loading, MatchList, PageTitle, useCatalog } from "@/components/ui";

export default function CalendarPage() {
  const cat = useCatalog();
  const [comp, setComp] = useState("");
  const q = `/matches?date_from=${encodeURIComponent(dayStart(0))}&date_to=${encodeURIComponent(dayStart(15))}&limit=500${comp ? `&competition_id=${comp}` : ""}`;
  const { data, error, loading } = useApi<Match[]>(q);

  const byDay = new Map<string, Match[]>();
  for (const m of data ?? []) {
    const k = new Date(m.kickoff_at).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
    byDay.set(k, [...(byDay.get(k) ?? []), m]);
  }
  return (
    <>
      <PageTitle title="Calendrier sportif" subtitle="15 prochains jours." />
      <select aria-label="Compétition" value={comp} onChange={(e) => setComp(e.target.value)} className="input mb-4 max-w-xs">
        <option value="">Toutes les compétitions</option>
        {cat.comps?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
      {error && <ErrorBox message={error} />}
      {loading ? <Loading what="matchs" /> : byDay.size === 0 ? <Empty>Aucun match enregistré sur cette période.</Empty> :
        [...byDay].map(([day, ms]) => (
          <section key={day} className="mb-5"><h2 className="mb-2 text-sm font-medium capitalize text-muted">{day}</h2><MatchList matches={ms} cat={cat} /></section>
        ))}
    </>
  );
}
