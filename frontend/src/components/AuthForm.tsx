"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { setToken } from "@/lib/session";
import { ErrorBox } from "@/components/ui";

export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const email = String(f.get("email")), password = String(f.get("password"));
    setBusy(true); setError(null);
    try {
      if (mode === "register")
        await api("/auth/register", { method: "POST", json: { email, password, display_name: String(f.get("display_name")) } });
      const t = await api<{ access_token: string }>("/auth/login", { method: "POST", form: { username: email, password } });
      setToken(t.access_token);
      router.replace("/dashboard");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-4 py-10">
      <p className="font-mono text-sm tracking-widest text-accent">PREDIX AI</p>
      <h1 className="mt-2 text-2xl font-semibold">{mode === "login" ? "Connexion" : "Créer un compte"}</h1>
      <form onSubmit={onSubmit} className="mt-6 space-y-3">
        {mode === "register" && (
          <label className="block text-sm">Nom affiché
            <input name="display_name" required minLength={2} maxLength={100} className="input mt-1" autoComplete="name" /></label>
        )}
        <label className="block text-sm">Email
          <input name="email" type="email" required className="input mt-1" autoComplete="email" /></label>
        <label className="block text-sm">Mot de passe
          <input name="password" type="password" required minLength={mode === "register" ? 10 : 1} maxLength={72}
            className="input mt-1" autoComplete={mode === "login" ? "current-password" : "new-password"} /></label>
        {mode === "register" && <p className="text-xs text-muted">10 caractères minimum. Le premier compte créé devient administrateur.</p>}
        {error && <ErrorBox message={error} />}
        <button className="btn w-full" disabled={busy}>{busy ? "…" : mode === "login" ? "Se connecter" : "S'inscrire"}</button>
      </form>
      <p className="mt-4 text-sm text-muted">
        {mode === "login" ? <>Pas de compte ? <Link className="text-accent" href="/register">S&apos;inscrire</Link></>
          : <>Déjà inscrit ? <Link className="text-accent" href="/login">Se connecter</Link></>}
      </p>
    </main>
  );
}
