"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ApiError, uploadFile, type User } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { Alert, LevelBadge, SkeletonList, Tabs, useConfirm, useToast, ago, fmtDateTime } from "@/components/kit";
import { Empty, PageTitle } from "@/components/ui";

type Item = { code: string; name: string; country: string; kind: "main" | "extra"; followed: boolean; last_update_at: string | null; last_status: string | null };
type JobResult = { label: string; status: "ok" | "erreur" | "absent"; created?: number; updated?: number; skipped?: number; warnings?: string[]; message?: string };
type Job = { status: "running" | "done" | "error"; progress?: string; results?: JobResult[]; message?: string };
type Report = { rows: number; created_matches: number; updated_matches: number; skipped_duplicates: number; created_teams: number; created_competitions: number; enriched_odds: number; warnings: string[]; dry_run: boolean; source_format: string };
type FileRes = { name: string; report?: Report; errors?: { line: number; error: string }[]; message?: string };
type Batch = { id: number; created_at: string; source: string; label: string; rows: number; created_matches: number; updated_matches: number; skipped: number; status: string };
type League = { id: number; name: string };
type Quality = { competition: string; seasons: { season: string; matches: number; finished: number; scheduled: number; teams: number; closing_odds_pct: number | null; shots_pct: number | null }[];
  issues: { level: "error" | "warning" | "info"; message: string; hint: string }[]; counts: Record<string, number>; last_result_days: number | null; upcoming: number };
type Dup = { a: { id: number; name: string; matches: number }; b: { id: number; name: string; matches: number }; score: number };
type TabId = "catalog" | "import" | "history" | "quality" | "teams";

export default function DataHub() {
  const me = useApi<User>("/auth/me");
  const [tab, setTab] = useState<TabId>("catalog");
  if (me.loading) return <SkeletonList rows={3} />;
  if (me.data?.role !== "admin") return <Empty>Le Centre de données est réservé aux administrateurs.</Empty>;
  return (
    <>
      <PageTitle title="Centre de données" subtitle="Ajoutez des championnats, importez des historiques, contrôlez la qualité et corrigez les erreurs." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "catalog", label: "Championnats" }, { id: "import", label: "Importer des fichiers" }, { id: "history", label: "Historique des imports" }, { id: "quality", label: "Qualité" }, { id: "teams", label: "Équipes" }]} />
      {tab === "catalog" && <Catalog />}
      {tab === "import" && <ImportFiles />}
      {tab === "history" && <History />}
      {tab === "quality" && <QualityTab />}
      {tab === "teams" && <TeamsTab />}
    </>
  );
}

/* ---------- Championnats : ajout en un clic, mise à jour ---------- */
function Catalog() {
  const cat = useApi<Item[]>("/sources/catalog");
  const toast = useToast();
  const confirm = useConfirm();
  const [job, setJob] = useState<Job | null>(null);
  const [seasons, setSeasons] = useState(3);
  const [q, setQ] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const { reload } = cat;

  // Interrogation de la tâche en cours (démarrage / arrêt gérés par l'effet).
  useEffect(() => {
    if (!jobId) return;
    const t = setInterval(async () => {
      try {
        const j = await api<Job>(`/sources/jobs/${jobId}`);
        setJob(j);
        if (j.status !== "running") {
          clearInterval(t);
          setJobId(null);
          reload();
          const bad = j.results?.filter((r) => r.status === "erreur").length ?? 0;
          toast(j.status === "error" || bad ? "error" : "ok", j.status === "error" ? (j.message ?? "Échec") : bad ? `Terminé avec ${bad} erreur(s) : voir le détail.` : "Données à jour.");
        }
      } catch (e) {
        clearInterval(t);
        setJobId(null);
        setJob({ status: "error", message: (e as Error).message });
      }
    }, 1500);
    return () => clearInterval(t);
  }, [jobId, reload, toast]);

  async function start(path: string, body?: object) {
    try { const r = await api<{ job_id: string }>(path, { method: "POST", json: body }); setJob({ status: "running", progress: "démarrage" }); setJobId(r.job_id); } catch (e) { toast("error", (e as Error).message); }
  }
  async function add(it: Item) {
    if (await confirm({ title: `Ajouter ${it.name} (${it.country}) ?`, message: `Télécharge les ${seasons} dernière(s) saison(s) depuis football-data.co.uk (gratuit, usage personnel). Un fichier invalide est refusé en bloc et signalé.`, confirmLabel: "Télécharger" })) start("/sources/leagues", { code: it.code, seasons });
  }
  async function unfollow(it: Item) {
    if (!(await confirm({ title: `Ne plus suivre ${it.name} ?`, message: "Les données déjà importées sont conservées ; seules les mises à jour automatiques s'arrêtent." }))) return;
    try { await api(`/sources/leagues/${it.code}`, { method: "DELETE" }); cat.reload(); } catch (e) { toast("error", (e as Error).message); }
  }
  const list = useMemo(() => (cat.data ?? []).filter((c) => !q || `${c.name} ${c.country} ${c.code}`.toLowerCase().includes(q.toLowerCase())), [cat.data, q]);
  const running = job?.status === "running";
  const followed = (cat.data ?? []).filter((c) => c.followed).length;

  return (
    <>
      <Alert kind="info">Source : football-data.co.uk (gratuit, usage personnel). L&apos;application télécharge elle-même les fichiers depuis votre ordinateur ; il faut une connexion Internet. Les championnats ajoutés sont ensuite mis à jour d&apos;un clic (résultats + prochains matchs avec cotes).</Alert>
      <div className="card mb-4 flex flex-wrap items-center gap-3">
        <button className="btn" disabled={running || followed === 0} onClick={() => start("/sources/update")}>⟳ Tout mettre à jour</button>
        <span className="text-sm text-muted">{followed} championnat(s) suivi(s)</span>
        <label className="ml-auto flex items-center gap-2 text-sm">Saisons à l&apos;ajout
          <select className="input w-auto" value={seasons} onChange={(e) => setSeasons(Number(e.target.value))} aria-label="Nombre de saisons">{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select></label>
      </div>
      {job && (
        <div className="card mb-4" aria-live="polite">
          <p className="font-medium">{job.status === "running" ? `⏳ En cours — ${job.progress}` : job.status === "error" ? "✗ Échec" : "✓ Terminé"}</p>
          {job.message && <p className="mt-1 text-sm text-red-300">{job.message}</p>}
          {job.results && job.results.length > 0 && (
            <table className="tbl mt-2"><thead><tr><th>Fichier</th><th>Résultat</th><th>Détail</th></tr></thead><tbody>
              {job.results.map((r, i) => (
                <tr key={i}><td>{r.label}</td><td><span className={`badge ${r.status === "ok" ? "border-accent/50 text-accent" : r.status === "erreur" ? "border-red-500/50 text-red-300" : ""}`}>{r.status === "ok" ? "importé" : r.status === "absent" ? "absent (pas de fichier)" : "erreur"}</span></td>
                  <td className="text-xs text-muted">{r.status === "ok" ? `${r.created} créé(s), ${r.updated} complété(s), ${r.skipped} déjà connu(s)` : r.message ?? ""}{r.warnings?.map((w) => <span key={w} className="block text-yellow-300">⚠ {w}</span>)}</td></tr>))}
            </tbody></table>)}
        </div>)}
      <input className="input mb-3 max-w-sm" placeholder="Filtrer (pays, nom, code)…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filtrer les championnats" />
      {cat.loading ? <SkeletonList /> : (["main", "extra"] as const).map((kind) => (
        <section key={kind} className="mb-5">
          <h2 className="mb-2 font-medium">{kind === "main" ? "Championnats principaux (Europe)" : "Autres pays (Amérique, Asie, Nord de l'Europe…)"}</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {list.filter((c) => c.kind === kind).map((c) => (
              <div key={c.code} className="card flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{c.name} <span className="text-muted">· {c.country}</span></p>
                  <p className="truncate text-xs text-muted">{c.followed ? `Suivi · ${ago(c.last_update_at)}${c.last_status ? ` · ${c.last_status}` : ""}` : `Code ${c.code}`}</p>
                </div>
                {c.followed ? <><button className="btn-ghost" disabled={running} onClick={() => start("/sources/leagues", { code: c.code, seasons: 1 })}>Actualiser</button><button className="btn-ghost" onClick={() => unfollow(c)} aria-label={`Ne plus suivre ${c.name}`}>✕</button></>
                  : <button className="btn" disabled={running} onClick={() => add(c)}>Ajouter</button>}
              </div>))}
          </div>
        </section>))}
    </>
  );
}

/* ---------- Import de fichiers (plusieurs à la fois) ---------- */
function ImportFiles() {
  const toast = useToast();
  const [files, setFiles] = useState<File[]>([]);
  const [res, setRes] = useState<FileRes[]>([]);
  const [busy, setBusy] = useState(false);
  async function run(dry: boolean) {
    if (!files.length) return toast("error", "Choisissez au moins un fichier CSV.");
    setBusy(true); setRes([]);
    const out: FileRes[] = [];
    for (const f of files) {
      try { out.push({ name: f.name, report: await uploadFile<Report>(`/import/matches?dry_run=${dry}`, f) }); }
      catch (e) {
        const d = (e as ApiError & { detail?: { errors?: { line: number; error: string }[] } }).detail;
        out.push({ name: f.name, errors: d?.errors, message: (e as Error).message });
      }
      setRes([...out]);
    }
    setBusy(false);
    const bad = out.filter((o) => !o.report).length;
    toast(bad ? "error" : "ok", bad ? `${bad} fichier(s) refusé(s), rien n'a été écrit pour eux.` : dry ? "Vérification réussie : aucun fichier n'a été modifié." : "Import terminé.");
  }
  return (
    <>
      <Alert kind="info">Formats reconnus automatiquement : fichiers football-data.co.uk (principaux, « autres pays », prochains matchs) et format PREDIX. <b>Tout-ou-rien par fichier</b> : une ligne invalide annule le fichier. Commencez par « Vérifier » : rien n&apos;est écrit. Un import réel reste <b>annulable</b> (onglet Historique).</Alert>
      <div className="card mb-4 flex flex-wrap items-center gap-2">
        <input type="file" multiple accept=".csv,text/csv" className="input max-w-sm" aria-label="Fichiers CSV" onChange={(e) => { setFiles([...(e.target.files ?? [])]); setRes([]); }} />
        <button className="btn-ghost" disabled={busy || !files.length} onClick={() => run(true)}>1. Vérifier sans importer</button>
        <button className="btn" disabled={busy || !files.length} onClick={() => run(false)}>2. Importer {files.length > 1 ? `${files.length} fichiers` : ""}</button>
        {files.length > 0 && <span className="text-xs text-muted">{files.map((f) => f.name).join(", ")}</span>}
      </div>
      {res.map((r) => (
        <div key={r.name} className={`card mb-3 ${r.report ? "" : "border-red-500/40"}`}>
          <p className="font-medium">{r.name} {r.report ? <span className="badge ml-1 border-accent/50 text-accent">{r.report.dry_run ? "valide (non importé)" : "importé"}</span> : <span className="badge ml-1 border-red-500/50 text-red-300">refusé</span>}</p>
          {r.report && <p className="mt-1 text-sm text-muted">Format : {r.report.source_format} · {r.report.created_matches} créé(s), {r.report.updated_matches} complété(s) avec leur résultat, {r.report.skipped_duplicates} déjà connu(s), {r.report.created_teams} équipe(s) et {r.report.created_competitions} compétition(s) créée(s){r.report.enriched_odds ? `, ${r.report.enriched_odds} jeu(x) de cotes ajouté(s)` : ""}.</p>}
          {r.message && <p className="mt-1 text-sm text-red-300">{r.message}</p>}
          {r.errors && <ul className="mt-1 max-h-40 overflow-auto text-xs text-red-300">{r.errors.slice(0, 30).map((e) => <li key={e.line}>Ligne {e.line} : {e.error}</li>)}</ul>}
          {r.report?.warnings.map((w) => <p key={w} className="mt-1 text-xs text-yellow-300">⚠ {w}</p>)}
        </div>))}
    </>
  );
}

/* ---------- Historique des imports + annulation ---------- */
function History() {
  const { data, loading, reload } = useApi<Batch[]>("/imports");
  const toast = useToast();
  const confirm = useConfirm();
  async function rollback(b: Batch) {
    if (!(await confirm({ title: "Annuler cet import ?", danger: true, confirmLabel: "Supprimer les matchs importés",
      message: `« ${b.label} » : ${b.created_matches} match(s) créé(s) seront supprimés (avec leurs statistiques et cotes).\nImpossible si des prédictions enregistrées les concernent. Les équipes créées restent (nettoyage : onglet Équipes).` }))) return;
    try { const r = await api<{ deleted_matches: number }>(`/imports/${b.id}/rollback`, { method: "POST" }); toast("ok", `${r.deleted_matches} match(s) supprimé(s).`); reload(); } catch (e) { toast("error", (e as Error).message); }
  }
  if (loading) return <SkeletonList />;
  if (!data?.length) return <Empty>Aucun import enregistré.</Empty>;
  return (
    <div className="card overflow-x-auto"><table className="tbl min-w-[40rem]"><thead><tr><th>Date</th><th>Source</th><th>Fichier</th><th>Créés</th><th>Complétés</th><th>Déjà connus</th><th></th></tr></thead><tbody>
      {data.map((b) => (
        <tr key={b.id}><td>{fmtDateTime(b.created_at)}</td><td><span className="badge">{{ upload: "fichier", download: "téléchargé", fixtures: "prochains matchs" }[b.source] ?? b.source}</span></td><td className="max-w-[14rem] truncate">{b.label}</td>
          <td>{b.created_matches}</td><td>{b.updated_matches}</td><td>{b.skipped}</td>
          <td className="text-right">{b.status === "active" ? (b.created_matches > 0 ? <button className="btn-danger" onClick={() => rollback(b)}>Annuler</button> : null) : <span className="badge">annulé</span>}</td></tr>))}
    </tbody></table></div>
  );
}

/* ---------- Qualité des données ---------- */
function QualityTab() {
  const leagues = useApi<League[]>("/leagues");
  const [pick, setPick] = useState("");
  const id = pick || (leagues.data?.[0] ? String(leagues.data[0].id) : "");
  const q = useApi<Quality>(id ? `/quality/${id}` : null);
  if (leagues.loading) return <SkeletonList rows={2} />;
  if (!leagues.data?.length) return <Empty>Aucun championnat : ajoutez-en un dans l&apos;onglet Championnats.</Empty>;
  return (
    <>
      <select className="input mb-4 max-w-sm" aria-label="Championnat" value={id} onChange={(e) => setPick(e.target.value)}>{leagues.data.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select>
      {q.loading || !q.data ? <SkeletonList rows={3} /> : (<>
        <div className="mb-4 flex flex-wrap gap-2 text-sm">
          <span className="badge border-red-500/50 text-red-300">{q.data.counts.error} erreur(s)</span><span className="badge border-yellow-500/50 text-yellow-300">{q.data.counts.warning} à vérifier</span><span className="badge">{q.data.counts.info} info(s)</span>
          <span className="badge">{q.data.upcoming} match(s) à venir</span>{q.data.last_result_days !== null && <span className="badge">dernier résultat il y a {q.data.last_result_days} j</span>}
        </div>
        {q.data.issues.length === 0 ? <Alert kind="info">✓ Aucune anomalie détectée sur {q.data.competition}.</Alert> : (
          <ul className="mb-4 space-y-2">{q.data.issues.map((i, k) => (<li key={k} className="card flex gap-3"><LevelBadge level={i.level} /><div><p className="text-sm">{i.message}</p>{i.hint && <p className="text-xs text-muted">→ {i.hint}</p>}</div></li>))}</ul>)}
        <div className="card overflow-x-auto"><h2 className="mb-2 font-medium">Couverture par saison</h2><table className="tbl min-w-[32rem]"><thead><tr><th>Saison</th><th>Matchs</th><th>Terminés</th><th>À venir</th><th>Équipes</th><th>Cotes de clôture</th><th>Tirs</th></tr></thead><tbody>
          {q.data.seasons.map((s) => (<tr key={s.season}><td>{s.season}</td><td>{s.matches}</td><td>{s.finished}</td><td>{s.scheduled}</td><td>{s.teams}</td><td>{s.closing_odds_pct ?? "—"}{s.closing_odds_pct !== null && " %"}</td><td>{s.shots_pct ?? "—"}{s.shots_pct !== null && " %"}</td></tr>))}
        </tbody></table></div></>)}
    </>
  );
}

/* ---------- Doublons d'équipes ---------- */
function TeamsTab() {
  const { data, loading, reload } = useApi<Dup[]>("/teams/duplicates");
  const toast = useToast();
  const confirm = useConfirm();
  async function merge(keep: Dup["a"], rem: Dup["a"]) {
    if (!(await confirm({ title: "Fusionner ces deux équipes ?", danger: true, confirmLabel: `Garder « ${keep.name} »`,
      message: `« ${rem.name} » (${rem.matches} match(s)) sera fusionnée dans « ${keep.name} » (${keep.matches} match(s)). Ses matchs sont transférés et ce nom sera reconnu automatiquement aux prochains imports.\nÀ ne faire que s'il s'agit bien de la même équipe.` }))) return;
    try { const r = await api<{ matches_reassigned: number }>("/teams/merge", { method: "POST", json: { keep_id: keep.id, remove_id: rem.id } }); toast("ok", `Fusion faite (${r.matches_reassigned} match(s) transféré(s)).`); reload(); } catch (e) { toast("error", (e as Error).message); }
  }
  async function cleanup() {
    if (!(await confirm({ title: "Supprimer les équipes et compétitions sans aucun match ?", danger: true, confirmLabel: "Nettoyer" }))) return;
    try { const r = await api<{ teams: number; competitions: number }>("/admin/cleanup", { method: "POST" }); toast("ok", `${r.teams} équipe(s) et ${r.competitions} compétition(s) supprimée(s).`); reload(); } catch (e) { toast("error", (e as Error).message); }
  }
  return (
    <>
      <Alert kind="info">Deux noms proches (ex. « Man Utd » et « Manchester United ») venant de sources différentes faussent les statistiques. Deux équipes qui jouent dans la même compétition ne sont jamais proposées : ce sont forcément des équipes distinctes.</Alert>
      <div className="mb-4"><button className="btn-ghost" onClick={cleanup}>Nettoyer les équipes sans match</button></div>
      {loading ? <SkeletonList /> : !data?.length ? <Empty>✓ Aucun doublon probable détecté.</Empty> : (
        <ul className="space-y-2">{data.map((d) => (
          <li key={`${d.a.id}-${d.b.id}`} className="card flex flex-wrap items-center gap-3">
            <div className="min-w-0 flex-1 text-sm"><b>{d.a.name}</b> <span className="text-muted">({d.a.matches})</span> ≈ <b>{d.b.name}</b> <span className="text-muted">({d.b.matches})</span> <span className="badge ml-1">{Math.round(d.score * 100)} %</span></div>
            <button className="btn-ghost" onClick={() => merge(d.a, d.b)}>Garder « {d.a.name} »</button><button className="btn-ghost" onClick={() => merge(d.b, d.a)}>Garder « {d.b.name} »</button>
          </li>))}</ul>)}
    </>
  );
}
