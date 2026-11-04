"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { Alert, SkeletonList, fmtDateTime, useToast } from "@/components/kit";

type Settings = { auto_enabled: boolean; auto_interval_hours: number; auto_record: boolean; auto_record_hours: number; odds_api_key_set: boolean; odds_api_every_hours: number; odds_api_remaining: string | null };
type Run = { id: number; started_at: string; finished_at: string | null; trigger: string; status: string; summary: Record<string, Record<string, unknown>> | null };
type Status = { settings: Settings; running: boolean; next_run_at: string | null; runs: Run[] };

function line(r: Run): string {
  const s = r.summary ?? {};
  const u = s.update as { created?: number; updated?: number; errors?: string[] } | undefined;
  const p = s.predictions as { recorded?: number; no_model?: number } | undefined;
  const o = s.odds as { odds_added?: number; skipped?: string } | undefined;
  return [u ? `${u.created ?? 0} match(s) ajouté(s), ${u.updated ?? 0} complété(s)` : null, o?.odds_added !== undefined ? `${o.odds_added} cote(s) The Odds API` : null,
    p ? `${p.recorded ?? 0} prédiction(s) enregistrée(s)` : null, (s.settled as { count?: number } | undefined)?.count ? `${(s.settled as { count: number }).count} réglée(s)` : null,
    u?.errors?.length ? `⚠ ${u.errors.length} erreur(s)` : null].filter(Boolean).join(" · ") || "rien à faire";
}

export default function AutomationPanel({ isAdmin }: { isAdmin: boolean }) {
  const { data, loading, reload } = useApi<Status>("/automation/status", { refreshMs: 15000 });
  const toast = useToast();
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  if (loading || !data) return <section className="card mb-4"><SkeletonList rows={2} /></section>;
  const st = data.settings;

  async function save(patch: Partial<Settings> & { odds_api_key?: string }, msg = "Réglage enregistré.") {
    setBusy(true);
    try { await api("/automation/settings", { method: "PUT", json: patch }); toast("ok", msg); reload(); } catch (e) { toast("error", (e as Error).message); }
    setBusy(false);
  }
  async function run() { try { await api("/automation/run", { method: "POST" }); toast("info", "Mise à jour lancée."); reload(); } catch (e) { toast("error", (e as Error).message); } }
  async function testKey() {
    try { const r = await api<{ soccer_competitions: number; remaining: string | null }>("/automation/odds-key/test", { method: "POST" }); toast("ok", `Clé valide : ${r.soccer_competitions} compétitions de football, ${r.remaining ?? "?"} crédits restants.`); reload(); }
    catch (e) { toast("error", (e as Error).message); }
  }

  return (
    <section className="card mb-4">
      <h2 className="mb-1 font-medium">Automatisation</h2>
      <p className="mb-3 text-xs text-muted">Quand l&apos;application est ouverte (PC allumé), elle met tout à jour toute seule : résultats, calendrier, cotes, prédictions et règlement.</p>
      {!isAdmin && <Alert kind="info">Seul un administrateur peut modifier ces réglages.</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={st.auto_enabled} disabled={!isAdmin || busy} onChange={(e) => save({ auto_enabled: e.target.checked })} /> Mise à jour automatique</label>
        <label className="flex items-center gap-2 text-sm">Toutes les <select className="input w-auto" disabled={!isAdmin || busy} value={st.auto_interval_hours} onChange={(e) => save({ auto_interval_hours: Number(e.target.value) })}>{[1, 3, 6, 12, 24].map((h) => <option key={h} value={h}>{h} h</option>)}</select></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={st.auto_record} disabled={!isAdmin || busy} onChange={(e) => save({ auto_record: e.target.checked })} /> Enregistrer automatiquement les prédictions (avant le match, immuables)</label>
        <label className="flex items-center gap-2 text-sm">pour les matchs des prochaines <select className="input w-auto" disabled={!isAdmin || busy} value={st.auto_record_hours} onChange={(e) => save({ auto_record_hours: Number(e.target.value) })}>{[12, 24, 48, 72, 168].map((h) => <option key={h} value={h}>{h} h</option>)}</select></label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
        {isAdmin && <button className="btn" disabled={data.running} onClick={run}>{data.running ? "En cours…" : "Lancer maintenant"}</button>}
        {data.next_run_at && st.auto_enabled && <span className="text-xs text-muted">Prochaine mise à jour : {fmtDateTime(data.next_run_at)}</span>}
      </div>

      <h3 className="mb-1 mt-5 text-sm font-medium">Cotes de plus de bookmakers (The Odds API, facultatif)</h3>
      <p className="mb-2 text-xs text-muted">Source officielle, gratuite jusqu&apos;à environ 500 requêtes par mois : https://the-odds-api.com (créez un compte, copiez la clé reçue par e-mail). Elle donne les cotes de nombreux bookmakers (dont 1xBet selon la région) pour les championnats suivis et les coupes. L&apos;application ne fait que <b>lire</b> les cotes. Sans clé, les cotes viennent de football-data.co.uk.</p>
      <div className="flex flex-wrap items-center gap-2">
        <input type="password" className="input max-w-xs" placeholder={st.odds_api_key_set ? "Clé enregistrée (masquée)" : "Collez votre clé"} value={key} disabled={!isAdmin} onChange={(e) => setKey(e.target.value)} autoComplete="off" aria-label="Clé The Odds API" />
        <button className="btn-ghost" disabled={!isAdmin || !key.trim() || busy} onClick={() => { save({ odds_api_key: key.trim() }, "Clé enregistrée."); setKey(""); }}>Enregistrer</button>
        {st.odds_api_key_set && <><button className="btn-ghost" disabled={!isAdmin} onClick={testKey}>Tester la clé</button><button className="btn-danger" disabled={!isAdmin || busy} onClick={() => save({ odds_api_key: "" }, "Clé effacée.")}>Effacer</button></>}
        {st.odds_api_remaining && <span className="text-xs text-muted">{st.odds_api_remaining} crédits restants</span>}
      </div>

      <h3 className="mb-1 mt-5 text-sm font-medium">Dernières exécutions</h3>
      {data.runs.length === 0 ? <p className="text-sm text-muted">Aucune exécution pour l&apos;instant.</p> : (
        <table className="tbl"><tbody>{data.runs.slice(0, 6).map((r) => (
          <tr key={r.id}><td className="whitespace-nowrap text-xs text-muted">{fmtDateTime(r.started_at)}</td><td><span className={`badge ${r.status === "ok" ? "border-accent/50 text-accent" : r.status === "partial" ? "border-yellow-500/50 text-yellow-300" : ""}`}>{r.status === "ok" ? "réussie" : r.status === "partial" ? "partielle" : r.status === "running" ? "en cours" : r.status}</span> <span className="text-xs text-muted">{r.trigger === "manual" ? "manuelle" : "auto"}</span></td><td className="text-xs text-muted">{line(r)}</td></tr>))}</tbody></table>)}
    </section>
  );
}
