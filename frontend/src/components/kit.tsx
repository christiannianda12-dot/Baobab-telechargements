"use client";

/** Boîte à outils d'interface : notifications, confirmations, onglets, pagination, graphiques légers. */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

// ---------- Notifications ----------
type Kind = "ok" | "error" | "info";
const ToastCtx = createContext<(kind: Kind, msg: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<{ id: number; kind: Kind; msg: string }[]>([]);
  const push = useCallback((kind: Kind, msg: string) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x.slice(-3), { id, kind, msg }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), kind === "error" ? 9000 : 4500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex flex-col items-center gap-2 px-4 md:bottom-6 md:items-end md:pr-6">
        {items.map((t) => (
          <div key={t.id} role={t.kind === "error" ? "alert" : "status"}
            className={`pointer-events-auto max-w-md rounded-lg border px-4 py-2.5 text-sm shadow-lg ${t.kind === "error" ? "border-red-500/50 bg-red-950 text-red-100" : t.kind === "ok" ? "border-accent/50 bg-emerald-950 text-emerald-100" : "border-border bg-surface"}`}>
            {t.msg}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

// ---------- Confirmation (actions destructrices) ----------
type ConfirmOpts = { title: string; message?: string; confirmLabel?: string; danger?: boolean };
const ConfirmCtx = createContext<(o: ConfirmOpts) => Promise<boolean>>(async () => false);
export const useConfirm = () => useContext(ConfirmCtx);

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [st, setSt] = useState<{ opts: ConfirmOpts; resolve: (v: boolean) => void } | null>(null);
  const confirm = useCallback((opts: ConfirmOpts) => new Promise<boolean>((resolve) => setSt({ opts, resolve })), []);
  const close = (v: boolean) => { st?.resolve(v); setSt(null); };
  return (
    <ConfirmCtx.Provider value={confirm}>
      {children}
      {st && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onKeyDown={(e) => e.key === "Escape" && close(false)}>
          <div role="dialog" aria-modal="true" aria-label={st.opts.title} className="card w-full max-w-md shadow-2xl">
            <h2 className="text-lg font-semibold">{st.opts.title}</h2>
            {st.opts.message && <p className="mt-2 whitespace-pre-line text-sm text-muted">{st.opts.message}</p>}
            <div className="mt-4 flex justify-end gap-2">
              <button autoFocus className="btn-ghost" onClick={() => close(false)}>Annuler</button>
              <button className={st.opts.danger ? "btn-danger" : "btn"} onClick={() => close(true)}>{st.opts.confirmLabel ?? "Confirmer"}</button>
            </div>
          </div>
        </div>
      )}
    </ConfirmCtx.Provider>
  );
}

// ---------- Onglets ----------
export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; badge?: string | number }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div role="tablist" className="mb-4 flex gap-1 overflow-x-auto border-b border-border">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} className="tab whitespace-nowrap" onClick={() => onChange(t.id)}>
          {t.label}{t.badge !== undefined && <span className="badge ml-1.5">{t.badge}</span>}
        </button>
      ))}
    </div>
  );
}

// ---------- Pagination ----------
export function Pagination({ total, limit, offset, onChange }: { total: number; limit: number; offset: number; onChange: (offset: number) => void }) {
  if (total <= limit) return <p className="mt-2 text-xs text-muted">{total} résultat(s)</p>;
  const page = Math.floor(offset / limit) + 1, pages = Math.ceil(total / limit);
  return (
    <div className="mt-3 flex items-center justify-between text-sm">
      <span className="text-xs text-muted">{offset + 1}–{Math.min(offset + limit, total)} sur {total}</span>
      <div className="flex items-center gap-2">
        <button className="btn-ghost" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>← Précédent</button>
        <span className="text-muted">{page}/{pages}</span>
        <button className="btn-ghost" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Suivant →</button>
      </div>
    </div>
  );
}

// ---------- Petits éléments ----------
export function Skeleton({ className = "h-4 w-full" }: { className?: string }) { return <div className={`skeleton ${className}`} aria-hidden />; }

export function SkeletonList({ rows = 4 }: { rows?: number }) {
  return <div className="space-y-2" aria-busy="true" aria-label="Chargement">{Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-14 w-full" />)}</div>;
}

export function StatCard({ label, value, hint, tone }: { label: string; value: React.ReactNode; hint?: string; tone?: "warn" | "ok" }) {
  return (
    <div className={`card ${tone === "warn" ? "border-yellow-500/40" : ""}`}>
      <p className="text-2xl font-semibold">{value}</p><p className="text-xs text-muted">{label}</p>{hint && <p className="mt-0.5 text-[11px] text-muted">{hint}</p>}
    </div>
  );
}

const CHIP = { W: "bg-emerald-500/25 text-emerald-200", D: "bg-zinc-500/30 text-zinc-200", L: "bg-red-500/25 text-red-200" } as const;
export function ResultChips({ results }: { results: string[] }) {
  return <span className="inline-flex gap-0.5" aria-label={`Forme : ${results.join(" ")}`}>{results.map((r, i) => <span key={i} className={`chip ${CHIP[r as "W" | "D" | "L"] ?? ""}`}>{r === "W" ? "V" : r === "D" ? "N" : "D"}</span>)}</span>;
}

export function LevelBadge({ level }: { level: "error" | "warning" | "info" }) {
  const c = { error: "border-red-500/50 text-red-300", warning: "border-yellow-500/50 text-yellow-300", info: "border-border text-muted" }[level];
  return <span className={`badge ${c}`}>{{ error: "Erreur", warning: "À vérifier", info: "Info" }[level]}</span>;
}

export function Alert({ kind = "warn", children }: { kind?: "warn" | "error" | "info"; children: React.ReactNode }) {
  const c = { warn: "border-yellow-500/40 bg-yellow-500/10 text-yellow-100", error: "border-red-500/40 bg-red-500/10 text-red-200", info: "border-border bg-surface text-muted" }[kind];
  return <div role={kind === "error" ? "alert" : "note"} className={`mb-4 rounded-lg border p-3 text-sm ${c}`}>{children}</div>;
}

// ---------- Graphiques (SVG, sans dépendance) ----------
type Series = { name: string; color: string; points: { x: number; y: number }[] };

export function LineChart({ series, height = 180, yFormat = (v: number) => v.toFixed(2), xLabels }: { series: Series[]; height?: number; yFormat?: (v: number) => string; xLabels?: [string, string] }) {
  const W = 600, H = height, P = { l: 44, r: 8, t: 8, b: 20 };
  const pts = series.flatMap((s) => s.points);
  if (pts.length < 2) return <p className="text-sm text-muted">Pas assez de points pour tracer la courbe.</p>;
  const xs = pts.map((p) => p.x), ys = [...pts.map((p) => p.y), 0];
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const sx = (x: number) => P.l + ((x - x0) / (x1 - x0 || 1)) * (W - P.l - P.r);
  const sy = (y: number) => H - P.b - ((y - y0) / (y1 - y0 || 1)) * (H - P.t - P.b);
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={series.map((s) => s.name).join(", ")}>
        {[y0, (y0 + y1) / 2, y1].map((v, i) => (<g key={i}><line x1={P.l} x2={W - P.r} y1={sy(v)} y2={sy(v)} stroke="var(--border)" strokeWidth="1" /><text x={P.l - 4} y={sy(v) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">{yFormat(v)}</text></g>))}
        <line x1={P.l} x2={W - P.r} y1={sy(0)} y2={sy(0)} stroke="var(--muted)" strokeDasharray="4 3" strokeWidth="1" />
        {series.map((s) => <polyline key={s.name} fill="none" stroke={s.color} strokeWidth="2" points={s.points.map((p) => `${sx(p.x)},${sy(p.y)}`).join(" ")} />)}
        {xLabels && (<><text x={P.l} y={H - 4} fontSize="10" fill="var(--muted)">{xLabels[0]}</text><text x={W - P.r} y={H - 4} textAnchor="end" fontSize="10" fill="var(--muted)">{xLabels[1]}</text></>)}
      </svg>
      <p className="mt-1 flex flex-wrap gap-3 text-xs text-muted">{series.map((s) => <span key={s.name}><span style={{ color: s.color }}>●</span> {s.name}</span>)}</p>
    </div>
  );
}

export function CalibrationChart({ model, market }: { model: { mean_predicted: number; observed_frequency: number; n: number }[]; market: { mean_predicted: number; observed_frequency: number; n: number }[] }) {
  const S = 220, P = 28, sc = (v: number) => P + v * (S - P - 8), sy = (v: number) => S - P - v * (S - P - 8);
  const line = (d: typeof model) => d.map((b) => `${sc(b.mean_predicted)},${sy(b.observed_frequency)}`).join(" ");
  return (
    <div>
      <svg viewBox={`0 0 ${S} ${S}`} className="mx-auto w-full max-w-xs" role="img" aria-label="Courbe de calibration">
        <rect x={P} y={8} width={S - P - 8} height={S - P - 8} fill="none" stroke="var(--border)" />
        <line x1={sc(0)} y1={sy(0)} x2={sc(1)} y2={sy(1)} stroke="var(--muted)" strokeDasharray="4 3" />
        <polyline fill="none" stroke="#9aa5a8" strokeWidth="2" points={line(market)} />
        <polyline fill="none" stroke="var(--accent)" strokeWidth="2" points={line(model)} />
        {model.map((b, i) => <circle key={i} cx={sc(b.mean_predicted)} cy={sy(b.observed_frequency)} r={Math.min(6, 2 + b.n / 120)} fill="var(--accent)" />)}
        <text x={S / 2} y={S - 6} textAnchor="middle" fontSize="9" fill="var(--muted)">probabilité annoncée</text>
        <text x={8} y={S / 2} fontSize="9" fill="var(--muted)" transform={`rotate(-90 8 ${S / 2})`} textAnchor="middle">fréquence observée</text>
      </svg>
      <p className="mt-1 text-center text-xs text-muted"><span className="text-accent">●</span> modèle · <span style={{ color: "#9aa5a8" }}>●</span> marché · pointillé = calibration parfaite</p>
    </div>
  );
}

// ---------- Utilitaires ----------
export function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  const t = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => { t.current = setTimeout(() => setV(value), ms); return () => { if (t.current) clearTimeout(t.current); }; }, [value, ms]);
  return v;
}

export const fmtDate = (iso: string) => new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
export const fmtDateTime = (iso: string) => new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
export const ago = (iso: string | null) => {
  if (!iso) return "jamais";
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  return d <= 0 ? "aujourd'hui" : d === 1 ? "hier" : `il y a ${d} jours`;
};

/** Info-bulle d'aide en langage simple : survol, focus clavier ou toucher. */
export function Hint({ children, label = "Aide" }: { children: React.ReactNode; label?: string }) {
  return (
    <span className="group relative ml-1 inline-block align-middle">
      <button type="button" aria-label={label} className="h-4 w-4 rounded-full border border-border text-[10px] leading-none text-muted hover:text-foreground focus:text-foreground">?</button>
      <span role="tooltip" className="pointer-events-none absolute left-1/2 top-5 z-30 hidden w-64 -translate-x-1/2 rounded-lg border border-border bg-surface p-2 text-xs font-normal text-foreground shadow-xl group-hover:block group-focus-within:block">{children}</span>
    </span>
  );
}

/** Barres de probabilité 1X2 compactes. */
export function ProbBar({ p, labels }: { p: { home: number; draw: number; away: number }; labels: [string, string] }) {
  const pc = (x: number) => `${Math.round(x * 100)}%`;
  return (
    <div aria-label={`${labels[0]} ${pc(p.home)}, nul ${pc(p.draw)}, ${labels[1]} ${pc(p.away)}`}>
      <div className="flex h-2 overflow-hidden rounded bg-border">
        <div className="bg-accent" style={{ width: pc(p.home) }} /><div className="bg-zinc-500" style={{ width: pc(p.draw) }} /><div className="bg-sky-500" style={{ width: pc(p.away) }} />
      </div>
      <div className="mt-0.5 flex justify-between text-[11px] text-muted"><span>{pc(p.home)}</span><span>nul {pc(p.draw)}</span><span>{pc(p.away)}</span></div>
    </div>
  );
}
