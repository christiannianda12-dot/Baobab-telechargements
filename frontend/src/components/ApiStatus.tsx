"use client";

import { useEffect, useState } from "react";
import { apiGet, type SystemInfo } from "@/lib/api";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; info: SystemInfo };

const MODE_LABEL = { manual: "Manuel", demo: "Démo (données fictives)", api: "API externes" };

export default function ApiStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    Promise.all([apiGet<{ status: string }>("/health"), apiGet<SystemInfo>("/system/info")])
      .then(([, info]) => !cancelled && setState({ kind: "ok", info }))
      .catch((e: Error) => !cancelled && setState({ kind: "error", message: e.message }));
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "loading") return <p className="text-muted">Connexion au backend…</p>;
  if (state.kind === "error")
    return (
      <p role="alert" className="text-red-400">
        Backend injoignable ({state.message}). Lancez l&apos;API : voir README.
      </p>
    );

  const { info } = state;
  return (
    <div className="space-y-4">
      <p className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full bg-accent" aria-hidden />
        API et base de données opérationnelles
      </p>
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
        <Item label="Mode de données" value={MODE_LABEL[info.data_mode]} />
        <Item label="Base" value={info.database} />
        <Item label="Environnement" value={info.environment} />
      </dl>
      <ul className="space-y-1 text-sm">
        {info.providers.map((p) => (
          <li key={p.code} className="flex justify-between border-b border-border py-1">
            <span>{p.name}</span>
            <span className={p.configured ? "text-accent" : "text-muted"}>
              {p.configured ? "clé configurée" : "désactivé (clé absente)"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <dt className="text-muted">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
