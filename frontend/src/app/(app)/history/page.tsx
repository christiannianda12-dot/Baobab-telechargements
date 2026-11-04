"use client";

import Link from "next/link";
import { useApi } from "@/lib/hooks";
import type { Match } from "@/lib/api";
import { Empty, ErrorBox, Loading, PageTitle, useCatalog } from "@/components/ui";

export type PredRow = { id: number; match_id: number; model: string; market: string; selection: string; line: number | null;
  probability: number; observed_odds: number | null; created_at: string; outcome: "win" | "loss" | "void" | null };

const OUT = { win: ["Gagné", "text-accent"], loss: ["Perdu", "text-red-300"], void: ["Annulé", "text-muted"] } as const;

export default function History() {
  const preds = useApi<PredRow[]>("/predictions?limit=500");
  const matches = useApi<Match[]>("/matches?limit=500");
  const cat = useCatalog();
  const byId = new Map((matches.data ?? []).map((m) => [m.id, m]));
  const groups = new Map<number, PredRow[]>();
  for (const p of preds.data ?? []) groups.set(p.match_id, [...(groups.get(p.match_id) ?? []), p]);

  return (
    <>
      <PageTitle title="Historique" subtitle="Prédictions enregistrées avant le coup d'envoi. Elles sont immuables : aucune modification ni suppression, garantie par la base de données." />
      {(preds.error || matches.error) && <ErrorBox message={(preds.error ?? matches.error)!} />}
      {preds.loading ? <Loading what="prédictions" /> : groups.size === 0 ? <Empty>Aucune prédiction enregistrée. Ouvrez un match à venir puis enregistrez sa prédiction.</Empty> :
        [...groups].map(([mid, rows]) => {
          const m = byId.get(mid);
          return (
            <section key={mid} className="card mb-3">
              <Link href={`/matches/${mid}`} className="font-medium text-accent">
                {m ? `${cat.team.get(m.home_team_id) ?? "?"} – ${cat.team.get(m.away_team_id) ?? "?"}` : `Match ${mid}`}</Link>
              <p className="mb-2 text-xs text-muted">Enregistrée le {new Date(rows[0].created_at).toLocaleString("fr-FR")} · modèle {rows[0].model}</p>
              <table className="w-full text-sm"><thead><tr className="text-left text-muted"><th>Marché</th><th>Proba</th><th>Cote saisie</th><th>Résultat</th></tr></thead>
                <tbody>{rows.map((r) => (
                  <tr key={r.id} className="border-t border-border"><td className="py-1">{r.market} {r.selection}{r.line !== null ? ` ${r.line}` : ""}</td>
                    <td>{(r.probability * 100).toFixed(1)} %</td><td>{r.observed_odds ?? "—"}</td>
                    <td className={r.outcome ? OUT[r.outcome][1] : "text-muted"}>{r.outcome ? OUT[r.outcome][0] : "En attente"}</td></tr>))}</tbody></table>
            </section>);
        })}
    </>
  );
}
