import Link from "next/link";
import { fmtDateTime } from "@/components/kit";

export type MatchItem = {
  id: number; kickoff_at: string; status: string; home_team_id: number; away_team_id: number; home: string; away: string;
  home_score: number | null; away_score: number | null; competition: string; season: string | null; source: string;
};
const STATUS: Record<string, string> = { scheduled: "À venir", live: "En cours", finished: "Terminé", postponed: "Reporté", cancelled: "Annulé" };

export default function MatchLine({ m, showLeague = true }: { m: MatchItem; showLeague?: boolean }) {
  const done = m.home_score !== null;
  return (
    <li>
      <Link href={`/matches/${m.id}`} className="card flex items-center gap-3 py-3 hover:border-accent">
        <span className="w-24 shrink-0 text-xs text-muted">{fmtDateTime(m.kickoff_at)}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{m.home} <span className={done ? "mx-1 font-mono text-accent" : "mx-1 text-muted"}>{done ? `${m.home_score} – ${m.away_score}` : "vs"}</span> {m.away}</span>
          {showLeague && <span className="block truncate text-xs text-muted">{m.competition}{m.season ? ` · ${m.season}` : ""}</span>}
        </span>
        <span className="hidden gap-1 sm:flex"><span className="badge">{STATUS[m.status] ?? m.status}</span>{m.source === "demo" && <span className="badge border-yellow-500/50 text-yellow-300">DÉMO</span>}</span>
      </Link>
    </li>
  );
}
