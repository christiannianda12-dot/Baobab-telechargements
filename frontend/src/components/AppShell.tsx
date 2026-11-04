"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import CommandPalette from "@/components/CommandPalette";
import StatusBar from "@/components/StatusBar";
import { ConfirmProvider, ToastProvider } from "@/components/kit";
import { useApi, useToken } from "@/lib/hooks";
import { logout, type User } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Tableau de bord", short: "Accueil", icon: "▦" },
  { href: "/matches", label: "Matchs", short: "Matchs", icon: "⚽" },
  { href: "/leagues", label: "Championnats", short: "Ligues", icon: "🏆" },
  { href: "/assistant", label: "Assistant IA", short: "Assistant", icon: "✦" },
  { href: "/combos", label: "Combinés", short: "Combinés", icon: "⊞" },
  { href: "/history", label: "Historique", short: "Historique", icon: "↺" },
  { href: "/performance", label: "Performance", short: "Perf.", icon: "◔" },
  { href: "/reliability", label: "Fiabilité", short: "Fiabilité", icon: "✓" },
  { href: "/data", label: "Centre de données", short: "Données", icon: "⇩", admin: true },
  { href: "/help", label: "Aide", short: "Aide", icon: "?" },
  { href: "/settings", label: "Paramètres", short: "Réglages", icon: "⚙" },
  { href: "/admin", label: "Administration", short: "Admin", icon: "⛨", admin: true },
];

// false côté serveur / pendant l'hydratation, true ensuite : évite de lire un jeton « vide » trop tôt.
const useMounted = () => useSyncExternalStore(() => () => {}, () => true, () => false);

export default function AppShell({ children }: { children: React.ReactNode }) {
  const token = useToken();
  const mounted = useMounted();
  const router = useRouter();
  const pathname = usePathname();
  const { data: user } = useApi<User>(token ? "/auth/me" : null);
  const [palette, setPalette] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = /INPUT|TEXTAREA|SELECT/.test((e.target as HTMLElement)?.tagName ?? "");
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((v) => !v); }
      else if (e.key === "/" && !typing) { e.preventDefault(); setPalette(true); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (mounted && !token) router.replace("/login");
  }, [mounted, token, router]);

  if (!mounted || !token) return <p className="p-6 text-muted">Chargement…</p>;
  const items = NAV.filter((n) => !n.admin || user?.role === "admin");
  const active = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <ToastProvider><ConfirmProvider>
    <CommandPalette open={palette} onClose={() => setPalette(false)} />
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-surface p-4 md:flex">
        <p className="mb-3 font-mono text-sm tracking-widest text-accent">PREDIX AI</p>
        <button onClick={() => setPalette(true)} className="mb-4 flex items-center justify-between rounded-lg border border-border px-3 py-2 text-left text-sm text-muted hover:text-foreground" aria-label="Recherche rapide">
          <span>🔍 Rechercher…</span><kbd className="rounded border border-border px-1 text-[10px]">Ctrl K</kbd>
        </button>
        <nav className="flex flex-1 flex-col gap-1" aria-label="Navigation principale">
          {items.map((n) => (
            <Link key={n.href} href={n.href} aria-current={active(n.href) ? "page" : undefined}
              className={`rounded-lg px-3 py-2 text-sm ${active(n.href) ? "bg-accent/15 text-accent" : "text-muted hover:text-foreground"}`}>
              <span className="mr-2" aria-hidden>{n.icon}</span>{n.label}
            </Link>
          ))}
        </nav>
        <div className="border-t border-border pt-3 text-xs text-muted">
          <p className="truncate">{user?.display_name ?? "…"}</p>
          <button className="mt-1 underline" onClick={logout}>Se déconnecter</button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col pb-16 md:pb-0">
        <StatusBar user={user} />
        <div className="flex items-center justify-between border-b border-border px-4 py-2 md:hidden">
          <span className="font-mono text-xs tracking-widest text-accent">PREDIX AI</span>
          <button className="btn-ghost" onClick={() => setPalette(true)} aria-label="Rechercher">🔍</button>
        </div>
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">{children}</main>
      </div>
      <nav aria-label="Navigation mobile"
        className="fixed inset-x-0 bottom-0 z-10 flex overflow-x-auto border-t border-border bg-surface md:hidden">
        {items.map((n) => (
          <Link key={n.href} href={n.href} aria-current={active(n.href) ? "page" : undefined}
            className={`flex min-w-[4.5rem] flex-1 flex-col items-center gap-0.5 px-2 py-2 text-[11px] ${active(n.href) ? "text-accent" : "text-muted"}`}>
            <span className="text-base" aria-hidden>{n.icon}</span>{n.short}
          </Link>
        ))}
      </nav>
    </div>
    </ConfirmProvider></ToastProvider>
  );
}
