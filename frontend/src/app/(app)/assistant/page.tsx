"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { ErrorBox, PageTitle } from "@/components/ui";

type Msg = { role: "user" | "assistant"; text: string; meta?: string };
const SUGGESTIONS = [
  "Quels sont les marchés les plus intéressants statistiquement ?",
  "Construis un combiné de trois rencontres en privilégiant les probabilités élevées.",
  "Que peux-tu faire ?",
];

/** Rendu sûr (sans HTML brut) : gras **...** et retours à la ligne. */
function Rich({ text }: { text: string }) {
  return (
    <>{text.split("\n").map((line, i) => (
      <p key={i} className={line.startsWith("-") || line.startsWith("⚠") ? "pl-2" : ""}>
        {line.split(/(\*\*[^*]+\*\*)/g).map((part, j) => part.startsWith("**") ? <b key={j}>{part.slice(2, -2)}</b> : part)}
      </p>))}</>
  );
}

export default function Assistant() {
  const status = useApi<{ llm_enabled: boolean; message: string }>("/assistant/status");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setMsgs((m) => [...m, { role: "user", text }]); setInput(""); setBusy(true); setErr(null);
    try {
      const r = await api<{ answer: string; intent: string; sources: string[] }>("/assistant/chat", { method: "POST", json: { message: text } });
      setMsgs((m) => [...m, { role: "assistant", text: r.answer, meta: `Intention : ${r.intent}${r.sources.length ? ` · sources : ${r.sources.join(", ")}` : ""}` }]);
    } catch (e) { setErr((e as Error).message); }
    setBusy(false);
    setTimeout(() => end.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  return (
    <>
      <PageTitle title="Assistant IA" subtitle="Interroge les données enregistrées et les résultats du moteur statistique." />
      {status.data && <p className="mb-3 rounded-lg border border-border bg-surface p-3 text-xs text-muted">
        <span className="badge mr-2">{status.data.llm_enabled ? "Modèle de langage actif" : "Mode règles"}</span>{status.data.message}</p>}
      <div className="mb-3 space-y-3" aria-live="polite">
        {msgs.length === 0 && <div className="flex flex-wrap gap-2">{SUGGESTIONS.map((s) => <button key={s} className="btn-ghost text-left" onClick={() => send(s)}>{s}</button>)}</div>}
        {msgs.map((m, i) => (
          <div key={i} className={`card text-sm ${m.role === "user" ? "ml-8 border-accent/40" : "mr-2"}`}>
            <Rich text={m.text} />{m.meta && <p className="mt-2 text-[11px] text-muted">{m.meta}</p>}</div>))}
        {busy && <p className="text-sm text-muted">Calcul en cours…</p>}
        <div ref={end} />
      </div>
      {err && <ErrorBox message={err} />}
      <form className="sticky bottom-16 flex gap-2 md:bottom-4" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} maxLength={1000} className="input" aria-label="Votre message"
          placeholder="Ex. : Analyse Arsenal contre Chelsea" />
        <button className="btn" disabled={busy || !input.trim()}>Envoyer</button>
      </form>
    </>
  );
}
