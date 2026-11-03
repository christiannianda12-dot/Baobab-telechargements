"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useApi, dayStart } from "@/lib/hooks";
import { Empty, ErrorBox, PageTitle } from "@/components/ui";
import { Pagination, SkeletonList, useDebounced } from "@/components/kit";
import MatchLine, { type MatchItem } from "@/components/MatchLine";
import type { League } from "../leagues/page";

type Preset = "today" | "upcoming" | "results" | "all";
const PRESETS: [Preset, string][] = [["today", "Aujourd'hui"], ["upcoming", "À venir"], ["results", "Résultats"], ["all", "Tout"]];
const LIMIT = 30;

function Explorer() {
  const params = useSearchParams();
  const leagues = useApi<League[]>("/leagues");
  const [preset, setPreset] = useState<Preset>("upcoming");
  const [league, setLeague] = useState(params.get("league") ?? "");
  const [team, setTeam] = useState("");
  const [offset, setOffset] = useState(0);
  const dteam = useDebounced(team.trim(), 300);

  const q = new URLSearchParams({ limit: String(LIMIT), offset: String(offset) });
  if (league) q.set("league_id", league);
  if (dteam) q.set("team", dteam);
  if (preset === "today") { q.set("date_from", dayStart(0)); q.set("date_to", dayStart(1)); q.set("order", "asc"); }
  if (preset === "upcoming") { q.set("status", "scheduled"); q.set("date_from", dayStart(0)); q.set("order", "asc"); }
  if (preset === "results") { q.set("status", "finished"); q.set("order", "desc"); }
  if (preset === "all") q.set("order", "desc");
  const { data, error, loading } = useApi<{ total: number; items: MatchItem[] }>(`/matches-search?${q}`);

  return (
    <>
      <PageTitle title="Matchs" subtitle="Recherchez dans tous les championnats enregistrés." />
      <div className="card mb-4 space-y-3">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Période">{PRESETS.map(([k, label]) => (
          <button key={k} className={preset === k ? "btn" : "btn-ghost"} aria-pressed={preset === k} onClick={() => { setPreset(k); setOffset(0); }}>{label}</button>))}</div>
        <div className="grid gap-2 sm:grid-cols-2">
          <select className="input" aria-label="Championnat" value={league} onChange={(e) => { setLeague(e.target.value); setOffset(0); }}>
            <option value="">Tous les championnats</option>{leagues.data?.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select>
          <input className="input" placeholder="Rechercher une équipe…" aria-label="Équipe" value={team} onChange={(e) => { setTeam(e.target.value); setOffset(0); }} />
        </div>
      </div>
      {error && <ErrorBox message={error} />}
      {loading ? <SkeletonList rows={6} /> : !data?.items.length ? (
        <Empty>Aucun match ne correspond à ces filtres.{preset !== "all" && " Essayez « Tout »."}</Empty>
      ) : (<>
        <ul className="space-y-2">{data.items.map((m) => <MatchLine key={m.id} m={m} />)}</ul>
        <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
      </>)}
    </>
  );
}

export default function MatchesPage() {
  return <Suspense fallback={<SkeletonList rows={6} />}><Explorer /></Suspense>;
}
