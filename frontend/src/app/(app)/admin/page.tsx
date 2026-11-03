"use client";

import { useState } from "react";
import { api, API_URL, type User } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { Empty, ErrorBox, Loading, PageTitle, useCatalog } from "@/components/ui";

export default function Admin() {
  const me = useApi<User>("/auth/me");
  if (me.loading) return <Loading />;
  if (me.data?.role !== "admin") return <Empty>Accès réservé aux administrateurs.</Empty>;
  return (<><PageTitle title="Administration" /><Users meId={me.data.id} /><CsvImport /><ManualEntry /></>);
}

function Users({ meId }: { meId: number }) {
  const users = useApi<User[]>("/admin/users");
  const [err, setErr] = useState<string | null>(null);
  async function patch(id: number, json: object) {
    setErr(null);
    try { await api(`/admin/users/${id}`, { method: "PATCH", json }); users.reload(); } catch (x) { setErr((x as Error).message); }
  }
  return (
    <section className="card mb-4">
      <h2 className="mb-2 font-medium">Utilisateurs</h2>
      {err && <ErrorBox message={err} />}
      {users.loading ? <Loading what="utilisateurs" /> : (
        <ul className="divide-y divide-border text-sm">
          {users.data?.map((u) => (
            <li key={u.id} className="flex flex-wrap items-center gap-2 py-2">
              <span className="min-w-0 flex-1 truncate">{u.display_name} <span className="text-muted">{u.email}</span></span>
              <span className="badge">{u.role}</span>{!u.is_active && <span className="badge">désactivé</span>}
              {u.id !== meId && <>
                <button className="btn-ghost" onClick={() => patch(u.id, { role: u.role === "admin" ? "user" : "admin" })}>{u.role === "admin" ? "Rétrograder" : "Promouvoir"}</button>
                <button className="btn-ghost" onClick={() => patch(u.id, { is_active: !u.is_active })}>{u.is_active ? "Désactiver" : "Réactiver"}</button></>}
            </li>))}
        </ul>)}
    </section>
  );
}

function ManualEntry() {
  const cat = useCatalog();
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  async function post(e: React.FormEvent<HTMLFormElement>, path: string, build: (f: FormData) => object, label: string) {
    e.preventDefault();
    const form = e.currentTarget;
    try { await api(path, { method: "POST", json: build(new FormData(form)) }); form.reset(); setMsg({ ok: true, text: `${label} ajouté(e).` }); cat.reload(); }
    catch (x) { setMsg({ ok: false, text: (x as Error).message }); }
  }
  const s = (f: FormData, k: string) => String(f.get(k) ?? "").trim() || null;
  return (
    <section className="card">
      <h2 className="mb-1 font-medium">Saisie manuelle (mode manuel)</h2>
      <p className="mb-3 text-xs text-muted">Seules les données que vous saisissez ici existent dans l&apos;application.</p>
      {msg && (msg.ok ? <p className="mb-2 text-sm text-accent">{msg.text}</p> : <ErrorBox message={msg.text} />)}
      <form className="mb-3 grid gap-2 sm:grid-cols-3" onSubmit={(e) => post(e, "/teams", (f) => ({ name: s(f, "name"), country: s(f, "country") }), "Équipe")}>
        <input name="name" required placeholder="Nom de l'équipe" className="input" /><input name="country" placeholder="Pays" className="input" /><button className="btn">Ajouter l&apos;équipe</button></form>
      <form className="mb-3 grid gap-2 sm:grid-cols-4" onSubmit={(e) => post(e, "/competitions", (f) => ({ name: s(f, "name"), country: s(f, "country"), season: s(f, "season") }), "Compétition")}>
        <input name="name" required placeholder="Compétition" className="input" /><input name="country" placeholder="Pays" className="input" />
        <input name="season" placeholder="Saison (2025-2026)" className="input" /><button className="btn">Ajouter la compétition</button></form>
      <form className="grid gap-2 sm:grid-cols-3" onSubmit={(e) => post(e, "/matches", (f) => ({
        competition_id: Number(f.get("c")), home_team_id: Number(f.get("h")), away_team_id: Number(f.get("a")), kickoff_at: new Date(String(f.get("k"))).toISOString() }), "Match")}>
        <select name="c" required className="input" aria-label="Compétition"><option value="">Compétition…</option>{cat.comps?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        <select name="h" required className="input" aria-label="Domicile"><option value="">Domicile…</option>{cat.teams?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
        <select name="a" required className="input" aria-label="Extérieur"><option value="">Extérieur…</option>{cat.teams?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
        <input name="k" type="datetime-local" required className="input sm:col-span-2" aria-label="Coup d'envoi" /><button className="btn">Ajouter le match</button></form>
    </section>
  );
}

type Report = { rows: number; created_matches: number; skipped_duplicates: number; created_teams: number; created_competitions: number; dry_run: boolean };

function CsvImport() {
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [errors, setErrors] = useState<{ line: number; error: string }[]>([]);
  const [fatal, setFatal] = useState<string | null>(null);

  async function run(e: React.FormEvent<HTMLFormElement>, dry: boolean) {
    e.preventDefault();
    const file = new FormData(e.currentTarget.form ?? e.currentTarget).get("file");
    if (!(file instanceof File) || !file.size) return setFatal("Choisissez un fichier CSV.");
    setBusy(true); setReport(null); setErrors([]); setFatal(null);
    const body = new FormData();
    body.append("file", file);
    try {
      const res = await fetch(`${API_URL}/api/v1/import/matches?dry_run=${dry}`, { method: "POST", body, credentials: "include" });
      const j = await res.json();
      if (res.ok) setReport(j);
      else if (j.detail?.errors) setErrors(j.detail.errors);
      else setFatal(typeof j.detail === "string" ? j.detail : "Import refusé.");
    } catch { setFatal("API injoignable."); }
    setBusy(false);
  }

  return (
    <section className="card mb-4">
      <h2 className="mb-1 font-medium">Import CSV de matchs terminés</h2>
      <p className="mb-3 text-xs text-muted">
        Tout-ou-rien : une seule ligne invalide annule l&apos;import. Cellule vide = donnée absente (jamais 0). Équipes et compétitions manquantes sont créées.{" "}
        <a className="text-accent underline" href="/modele-matchs.csv" download>Télécharger le modèle (en-têtes)</a>
      </p>
      <form className="flex flex-wrap items-center gap-2">
        <input name="file" type="file" accept=".csv,text/csv" className="input max-w-xs" aria-label="Fichier CSV" />
        <button type="button" className="btn-ghost" disabled={busy} onClick={(e) => run(e as never, true)}>Vérifier sans importer</button>
        <button type="button" className="btn" disabled={busy} onClick={(e) => run(e as never, false)}>Importer</button>
      </form>
      {fatal && <div className="mt-3"><ErrorBox message={fatal} /></div>}
      {report && (
        <p className="mt-3 text-sm text-accent">
          {report.dry_run ? "Vérification réussie (rien écrit) : " : "Import terminé : "}
          {report.created_matches} match(s), {report.created_teams} équipe(s), {report.created_competitions} compétition(s) créés ; {report.skipped_duplicates} doublon(s) ignoré(s).
        </p>
      )}
      {errors.length > 0 && (
        <div className="mt-3"><ErrorBox message={`${errors.length} erreur(s) — aucune ligne importée.`} />
          <ul className="mt-2 max-h-48 overflow-auto text-xs text-red-300">{errors.slice(0, 50).map((x) => <li key={x.line}>Ligne {x.line} : {x.error}</li>)}</ul></div>
      )}
    </section>
  );
}
