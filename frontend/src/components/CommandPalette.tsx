"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useDebounced } from "@/components/kit";

type Hit = { label: string; sub?: string; href: string };
const PAGES: Hit[] = [
  { label: "Tableau de bord", href: "/dashboard" }, { label: "Matchs", href: "/matches" }, { label: "Championnats", href: "/leagues" },
  { label: "Assistant IA", href: "/assistant" }, { label: "Combinés", href: "/combos" }, { label: "Historique", href: "/history" },
  { label: "Performance", href: "/performance" }, { label: "Fiabilité du modèle", href: "/reliability" }, { label: "Centre de données", href: "/data" },
  { label: "Aide et glossaire", href: "/help" }, { label: "Paramètres", href: "/settings" },
];

/** Recherche rapide : Ctrl+K (ou « / ») — pages, équipes, championnats. */
export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [remote, setRemote] = useState<{ q: string; hits: Hit[] }>({ q: "", hits: [] });
  const [sel, setSel] = useState(0);
  const dq = useDebounced(q.trim(), 200);

  useEffect(() => {
    if (!open || dq.length < 2) return;
    let cancelled = false;
    api<{ teams: { id: number; name: string }[]; leagues: { id: number; name: string }[] }>(`/search?q=${encodeURIComponent(dq)}`)
      .then((r) => !cancelled && setRemote({ q: dq, hits: [
        ...r.leagues.map((l) => ({ label: l.name, sub: "Championnat", href: `/leagues/${l.id}` })),
        ...r.teams.map((t) => ({ label: t.name, sub: "Équipe", href: `/teams/${t.id}` })),
      ] }))
      .catch(() => {});
    return () => { cancelled = true; };
  }, [dq, open]);

  const hits = useMemo(() => {
    const k = q.trim().toLowerCase();
    const pages = PAGES.filter((p) => !k || p.label.toLowerCase().includes(k)).map((p) => ({ ...p, sub: "Page" }));
    return [...(remote.q === dq ? remote.hits : []), ...pages].slice(0, 12);
  }, [q, dq, remote]);

  if (!open) return null;
  const go = (h?: Hit) => { if (h) { onClose(); setQ(""); router.push(h.href); } };
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 pt-[15vh]" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Recherche rapide" className="card w-full max-w-lg p-0 shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <input autoFocus className="input rounded-b-none border-0 border-b border-border text-base" placeholder="Rechercher une équipe, un championnat, une page…" value={q} aria-label="Rechercher"
          onChange={(e) => { setQ(e.target.value); setSel(0); }}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            else if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, hits.length - 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
            else if (e.key === "Enter") go(hits[sel]);
          }} />
        <ul className="max-h-80 overflow-auto p-1" role="listbox">
          {hits.length === 0 && <li className="p-3 text-sm text-muted">Aucun résultat.</li>}
          {hits.map((h, i) => (
            <li key={h.href + h.label} role="option" aria-selected={i === sel}>
              <button className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm ${i === sel ? "bg-accent/15 text-accent" : "hover:bg-background/60"}`} onMouseEnter={() => setSel(i)} onClick={() => go(h)}>
                <span>{h.label}</span><span className="text-xs text-muted">{h.sub}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="border-t border-border px-3 py-1.5 text-[11px] text-muted">↑↓ naviguer · Entrée ouvrir · Échap fermer</p>
      </div>
    </div>
  );
}
