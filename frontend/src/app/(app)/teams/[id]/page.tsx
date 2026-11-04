"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useApi } from "@/lib/hooks";
import { ErrorBox, PageTitle } from "@/components/ui";
import { ResultChips, SkeletonList, StatCard, fmtDateTime } from "@/components/kit";

type Game = { match_id: number; kickoff_at: string; status: string; home: boolean; opponent_id: number; opponent: string; score_for: number | null; score_against: number | null; result: string | null; competition: string };
type Form = { played: number; results: string[]; wins: number; draws: number; losses: number; goals_for: number; goals_against: number; avg_goals_for: number | null; avg_goals_against: number | null; averages: Record<string, { average: number | null; samples: number }> };
type Profile = { id: number; name: string; leagues: string[]; recent: Game[]; next: Game[]; elo: { rating: number; rank: number; of: number; league: string } | null; form: Record<"last5" | "last10" | "home" | "away", Form> };

export default function TeamPage() {
  const id = useParams<{ id: string }>().id;
  const { data: p, loading, error } = useApi<Profile>(`/teams/${id}/profile`);
  if (loading) return <SkeletonList rows={4} />;
  if (error || !p) return <ErrorBox message={error ?? "Équipe introuvable."} />;
  const F: [string, Form][] = [["5 derniers", p.form.last5], ["10 derniers", p.form.last10], ["À domicile", p.form.home], ["À l'extérieur", p.form.away]];
  return (
    <>
      <PageTitle title={p.name} subtitle={p.leagues.join(" · ")} />
      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label={p.elo ? `Classement Elo (${p.elo.league})` : "Classement Elo"} value={p.elo ? `${Math.round(p.elo.rating)}` : "—"} hint={p.elo ? `${p.elo.rank}ᵉ sur ${p.elo.of} équipes` : "Pas assez de matchs"} />
        <StatCard label="Forme (5 derniers)" value={<ResultChips results={p.form.last5.results} />} />
        <StatCard label="Buts marqués / match" value={p.form.last10.avg_goals_for ?? "—"} hint="10 derniers" />
        <StatCard label="Buts encaissés / match" value={p.form.last10.avg_goals_against ?? "—"} hint="10 derniers" />
      </div>
      {p.next.length > 0 && (
        <section className="mb-5"><h2 className="mb-2 font-medium">Prochains matchs</h2><ul className="space-y-2">{p.next.map((g) => (
          <li key={g.match_id}><Link href={`/matches/${g.match_id}`} className="card flex justify-between hover:border-accent"><span>{g.home ? "vs" : "@"} <b>{g.opponent}</b></span><span className="text-sm text-muted">{fmtDateTime(g.kickoff_at)}</span></Link></li>))}</ul></section>)}
      <section className="card mb-5 overflow-x-auto"><h2 className="mb-2 font-medium">Bilan</h2>
        <table className="tbl min-w-[28rem]"><thead><tr><th></th><th>J</th><th>V-N-D</th><th>Buts</th><th>Série</th></tr></thead><tbody>
          {F.map(([label, f]) => (<tr key={label}><td>{label}</td><td>{f.played}</td><td>{f.wins}-{f.draws}-{f.losses}</td><td>{f.goals_for}:{f.goals_against}</td><td><ResultChips results={f.results} /></td></tr>))}
        </tbody></table></section>
      <section className="card overflow-x-auto"><h2 className="mb-2 font-medium">Derniers résultats</h2>
        {p.recent.length === 0 ? <p className="text-sm text-muted">Aucun match terminé.</p> : (
          <table className="tbl min-w-[28rem]"><tbody>{p.recent.map((g) => (
            <tr key={g.match_id}><td className="text-xs text-muted">{fmtDateTime(g.kickoff_at)}</td><td>{g.home ? "vs" : "@"} <Link href={`/teams/${g.opponent_id}`} className="hover:text-accent">{g.opponent}</Link></td>
              <td><Link href={`/matches/${g.match_id}`} className="font-mono hover:text-accent">{g.score_for}–{g.score_against}</Link></td><td><ResultChips results={g.result ? [g.result] : []} /></td></tr>))}</tbody></table>)}
      </section>
    </>
  );
}
