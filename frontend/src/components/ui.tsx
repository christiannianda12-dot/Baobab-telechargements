"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useApi } from "@/lib/hooks";
import type { Competition, Match, Team } from "@/lib/api";

export function PageTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="mb-5">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
    </header>
  );
}

export function Loading({ what = "données" }: { what?: string }) {
  return <p className="text-sm text-muted">Chargement des {what}…</p>;
}

export function ErrorBox({ message }: { message: string }) {
  return <p role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{message}</p>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="card text-sm text-muted">{children}</p>;
}

/** Page d'une fonctionnalité prévue plus tard : honnête, aucune donnée simulée. */
export function Unavailable({ title, step, why }: { title: string; step: string; why: string }) {
  return (
    <>
      <PageTitle title={title} />
      <div className="card">
        <p className="badge inline-block">Non disponible · {step}</p>
        <p className="mt-3 text-sm text-muted">{why}</p>
      </div>
    </>
  );
}

export function SourceBadge({ source }: { source: string }) {
  const label = source === "demo" ? "DÉMO (fictif)" : source === "manual" ? "saisie manuelle" : "API";
  return <span className={`badge ${source === "demo" ? "border-yellow-500/50 text-yellow-300" : ""}`}>{label}</span>;
}

/** Équipes + compétitions indexées par id (pour afficher des noms à la place des identifiants). */
export function useCatalog() {
  const teams = useApi<Team[]>("/teams?limit=500");
  const comps = useApi<Competition[]>("/competitions");
  const maps = useMemo(
    () => ({
      team: new Map((teams.data ?? []).map((t) => [t.id, t.name])),
      comp: new Map((comps.data ?? []).map((c) => [c.id, c.name])),
    }),
    [teams.data, comps.data],
  );
  return { ...maps, teams: teams.data, comps: comps.data, loading: teams.loading || comps.loading,
    reload: () => { teams.reload(); comps.reload(); }, error: teams.error ?? comps.error };
}

const STATUS: Record<string, string> = {
  scheduled: "À venir", live: "En cours", finished: "Terminé", postponed: "Reporté", cancelled: "Annulé",
};

export function MatchRow({ m, cat }: { m: Match; cat: ReturnType<typeof useCatalog> }) {
  const time = new Date(m.kickoff_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  const score = m.home_score !== null ? `${m.home_score} – ${m.away_score}` : "vs";
  return (
    <li>
      <Link href={`/matches/${m.id}`} className="card flex items-center gap-3 hover:border-accent">
        <span className="w-12 font-mono text-sm text-muted">{time}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">
            {cat.team.get(m.home_team_id) ?? "?"} <span className="text-muted">{score}</span> {cat.team.get(m.away_team_id) ?? "?"}
          </span>
          <span className="block truncate text-xs text-muted">{cat.comp.get(m.competition_id) ?? "Compétition inconnue"}</span>
        </span>
        <span className="hidden gap-1 sm:flex"><span className="badge">{STATUS[m.status] ?? m.status}</span><SourceBadge source={m.source} /></span>
      </Link>
    </li>
  );
}

export function MatchList({ matches, cat }: { matches: Match[]; cat: ReturnType<typeof useCatalog> }) {
  return <ul className="space-y-2">{matches.map((m) => <MatchRow key={m.id} m={m} cat={cat} />)}</ul>;
}
