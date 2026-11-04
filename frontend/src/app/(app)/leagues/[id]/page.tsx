"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useApi } from "@/lib/hooks";
import { Empty, ErrorBox, PageTitle } from "@/components/ui";
import { Pagination, ResultChips, SkeletonList, Tabs } from "@/components/kit";
import MatchLine, { type MatchItem } from "@/components/MatchLine";
import type { League } from "../page";

type Row = { rank: number; team_id: number; team: string; played: number; won: number; drawn: number; lost: number; gf: number; ga: number; gd: number; points: number; form: string[] };
type Standings = { name: string; season: string | null; matches: number; table: Row[]; note: string };

export default function LeaguePage() {
  const id = Number(useParams<{ id: string }>().id);
  const leagues = useApi<League[]>("/leagues");
  const fam = leagues.data?.find((l) => l.seasons.some((s) => s.id === id));
  const [season, setSeason] = useState<number | null>(null);
  const [tab, setTab] = useState<"table" | "matches">("table");
  const [offset, setOffset] = useState(0);
  const sid = season ?? id;
  const st = useApi<Standings>(`/leagues/${sid}/standings`);
  const ms = useApi<{ total: number; items: MatchItem[] }>(tab === "matches" ? `/matches-search?competition_id=${sid}&limit=30&offset=${offset}&order=desc` : null);

  if (leagues.loading) return <SkeletonList rows={3} />;
  if (!fam) return <ErrorBox message="Championnat introuvable." />;
  return (
    <>
      <PageTitle title={fam.name} subtitle={`${fam.matches} matchs enregistrés sur ${fam.seasons.length} saison(s).`} />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select className="input w-auto" aria-label="Saison" value={sid} onChange={(e) => { setSeason(Number(e.target.value)); setOffset(0); }}>
          {fam.seasons.map((s) => <option key={s.id} value={s.id}>{s.season ?? "Sans saison"} ({s.finished} terminés{s.upcoming ? `, ${s.upcoming} à venir` : ""})</option>)}</select>
        <Link href={`/matches?league=${fam.id}`} className="btn-ghost">Tous les matchs →</Link>
      </div>
      <Tabs value={tab} onChange={(t) => { setTab(t); setOffset(0); }} tabs={[{ id: "table", label: "Classement" }, { id: "matches", label: "Matchs" }]} />
      {tab === "table" && (st.loading ? <SkeletonList /> : !st.data?.table.length ? <Empty>Aucun match terminé pour cette saison.</Empty> : (
        <div className="card overflow-x-auto p-2">
          <table className="tbl min-w-[34rem]"><thead><tr><th>#</th><th>Équipe</th><th>J</th><th>V</th><th>N</th><th>D</th><th>BP</th><th>BC</th><th>Diff</th><th>Pts</th><th>Forme</th></tr></thead><tbody>
            {st.data.table.map((r) => (
              <tr key={r.team_id}><td className="text-muted">{r.rank}</td><td><Link href={`/teams/${r.team_id}`} className="font-medium hover:text-accent">{r.team}</Link></td><td>{r.played}</td><td>{r.won}</td><td>{r.drawn}</td><td>{r.lost}</td><td>{r.gf}</td><td>{r.ga}</td>
                <td className={r.gd > 0 ? "text-accent" : r.gd < 0 ? "text-red-300" : ""}>{r.gd > 0 ? `+${r.gd}` : r.gd}</td><td className="font-semibold">{r.points}</td><td><ResultChips results={r.form} /></td></tr>))}
          </tbody></table>
          <p className="px-2 pb-1 pt-2 text-xs text-muted">{st.data.note}</p>
        </div>))}
      {tab === "matches" && (ms.loading ? <SkeletonList /> : !ms.data?.items.length ? <Empty>Aucun match.</Empty> : (<>
        <ul className="space-y-2">{ms.data.items.map((m) => <MatchLine key={m.id} m={m} showLeague={false} />)}</ul>
        <Pagination total={ms.data.total} limit={30} offset={offset} onChange={setOffset} />
      </>))}
    </>
  );
}
