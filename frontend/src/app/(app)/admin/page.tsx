"use client";

import { useState } from "react";
import Link from "next/link";
import { api, type User } from "@/lib/api";
import { useConfirm, useToast } from "@/components/kit";
import { useApi } from "@/lib/hooks";
import { Empty, ErrorBox, Loading, PageTitle, useCatalog } from "@/components/ui";

export default function Admin() {
  const me = useApi<User>("/auth/me");
  if (me.loading) return <Loading />;
  if (me.data?.role !== "admin") return <Empty>Accès réservé aux administrateurs.</Empty>;
  return (<><PageTitle title="Administration" /><Link href="/data" className="card mb-4 block hover:border-accent"><h2 className="font-medium">⇩ Centre de données</h2><p className="mt-1 text-sm text-muted">Ajouter des championnats, importer des fichiers, annuler un import, contrôler la qualité, fusionner les doublons.</p></Link>
      <Users meId={me.data.id} /><ManualEntry /></>);
}

function Users({ meId }: { meId: number }) {
  const users = useApi<User[]>("/admin/users");
  const [err, setErr] = useState<string | null>(null);
  const confirm = useConfirm();
  const toast = useToast();
  async function patch(id: number, json: object, ask: string) {
    if (!(await confirm({ title: ask, danger: true }))) return;
    setErr(null);
    try { await api(`/admin/users/${id}`, { method: "PATCH", json }); toast("ok", "Modification enregistrée."); users.reload(); } catch (x) { setErr((x as Error).message); toast("error", (x as Error).message); }
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
                <button className="btn-ghost" onClick={() => patch(u.id, { role: u.role === "admin" ? "user" : "admin" }, u.role === "admin" ? `Retirer les droits d'administrateur à ${u.display_name} ?` : `Donner les droits d'administrateur à ${u.display_name} ?`)}>{u.role === "admin" ? "Rétrograder" : "Promouvoir"}</button>
                <button className="btn-ghost" onClick={() => patch(u.id, { is_active: !u.is_active }, u.is_active ? `Désactiver le compte de ${u.display_name} ?` : `Réactiver le compte de ${u.display_name} ?`)}>{u.is_active ? "Désactiver" : "Réactiver"}</button></>}
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

