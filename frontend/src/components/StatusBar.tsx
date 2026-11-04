"use client";

import Link from "next/link";
import { api, type User } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { ago, fmtDateTime, useToast } from "@/components/kit";

type Status = { settings: { auto_enabled: boolean }; running: boolean; next_run_at: string | null; runs: { finished_at: string | null; status: string }[] };

/** Barre d'état : fraîcheur des données et mise à jour automatique (se rafraîchit toute seule). */
export default function StatusBar({ user }: { user?: User }) {
  const { data, reload } = useApi<Status>("/automation/status", { refreshMs: 20000 });
  const toast = useToast();
  if (!data) return null;
  const last = data.runs.find((r) => r.finished_at);
  const bad = last?.status === "partial";
  async function run() {
    try { await api("/automation/run", { method: "POST" }); toast("info", "Mise à jour lancée en arrière-plan."); reload(); } catch (e) { toast("error", (e as Error).message); }
  }
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border bg-surface/60 px-4 py-1.5 text-xs text-muted" role="status">
      <span className="flex items-center gap-1.5">
        <span className={`h-2 w-2 rounded-full ${data.running ? "animate-pulse bg-yellow-400" : data.settings.auto_enabled ? "bg-accent" : "bg-zinc-500"}`} aria-hidden />
        {data.running ? "Mise à jour en cours…" : data.settings.auto_enabled ? "Mise à jour automatique active" : "Mise à jour automatique désactivée"}
      </span>
      <span>Dernière : {last?.finished_at ? ago(last.finished_at) : "jamais"}{bad && <span className="text-yellow-300"> (incomplète)</span>}</span>
      {data.next_run_at && data.settings.auto_enabled && !data.running && <span className="hidden sm:inline">Prochaine : {fmtDateTime(data.next_run_at)}</span>}
      {user?.role === "admin" && <><button className="ml-auto underline hover:text-foreground disabled:opacity-50" disabled={data.running} onClick={run}>Mettre à jour maintenant</button><Link href="/settings" className="underline hover:text-foreground">Réglages</Link></>}
    </div>
  );
}
