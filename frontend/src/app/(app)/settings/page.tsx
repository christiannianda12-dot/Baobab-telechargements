"use client";

import ApiStatus from "@/components/ApiStatus";
import { PageTitle } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { setToken } from "@/lib/session";
import type { User } from "@/lib/api";

export default function Settings() {
  const { data: user } = useApi<User>("/auth/me");
  return (
    <>
      <PageTitle title="Paramètres" />
      <section className="card mb-4">
        <h2 className="mb-2 font-medium">Compte</h2>
        <p className="text-sm">{user?.display_name} · <span className="text-muted">{user?.email}</span></p>
        <p className="mt-1 text-xs text-muted">Rôle : {user?.role}</p>
        <button className="btn-ghost mt-3" onClick={() => setToken(null)}>Se déconnecter</button>
      </section>
      <section className="card">
        <h2 className="mb-3 font-medium">Système et fournisseurs de données</h2>
        <ApiStatus />
        <p className="mt-3 text-xs text-muted">Les clés API se configurent côté serveur (fichier .env), jamais dans le navigateur.</p>
      </section>
    </>
  );
}
