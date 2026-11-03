/** Client API. L'URL vient de NEXT_PUBLIC_API_URL ; aucune clé secrète ne passe par le frontend. */
import { setToken } from "@/lib/session";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type SystemInfo = {
  app: string;
  environment: string;
  data_mode: "manual" | "demo" | "api";
  database: string;
  providers: { code: string; name: string; kind: string; configured: boolean }[];
};
export type User = { id: number; email: string; display_name: string; role: "user" | "admin"; is_active?: boolean };
export type Team = { id: number; name: string; short_name: string | null; country: string | null; source: string };
export type Competition = { id: number; name: string; country: string | null; season: string | null; source: string };
export type Match = {
  id: number; competition_id: number; home_team_id: number; away_team_id: number;
  kickoff_at: string; status: string; home_score: number | null; away_score: number | null; source: string;
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown; form?: Record<string, string> } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  } else if (init.form) {
    body = new URLSearchParams(init.form);
  }
  const res = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers, body, cache: "no-store", credentials: "include" });
  if (!res.ok) {
    let detail = `Erreur ${res.status}`;
    try {
      const d = (await res.json()).detail;
      detail = typeof d === "string" ? d : Array.isArray(d) ? d.map((e: { msg: string }) => e.msg).join(" ; ") : detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

/** Déconnexion : l'API efface le cookie ; puis on retire l'indicateur local. */
export async function logout(): Promise<void> {
  try {
    await api("/auth/logout", { method: "POST" });
  } catch {}
  setToken(null);
}
