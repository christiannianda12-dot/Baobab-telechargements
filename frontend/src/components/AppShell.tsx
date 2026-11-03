"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";
import { useApi, useToken } from "@/lib/hooks";
import { logout, type User } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Tableau de bord", short: "Accueil", icon: "▦" },
  { href: "/matches", label: "Matchs du jour", short: "Matchs", icon: "⚽" },
  { href: "/calendar", label: "Calendrier", short: "Agenda", icon: "▤" },
  { href: "/assistant", label: "Assistant IA", short: "Assistant", icon: "✦" },
  { href: "/combos", label: "Combinés", short: "Combinés", icon: "⊞" },
  { href: "/history", label: "Historique", short: "Historique", icon: "↺" },
  { href: "/performance", label: "Performance", short: "Perf.", icon: "◔" },
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

  useEffect(() => {
    if (mounted && !token) router.replace("/login");
  }, [mounted, token, router]);

  if (!mounted || !token) return <p className="p-6 text-muted">Chargement…</p>;
  const items = NAV.filter((n) => !n.admin || user?.role === "admin");
  const active = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-surface p-4 md:flex">
        <p className="mb-6 font-mono text-sm tracking-widest text-accent">PREDIX AI</p>
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
        <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6">{children}</main>
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
  );
}
