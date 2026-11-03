/** Client API. L'URL vient de NEXT_PUBLIC_API_URL ; aucune clé secrète ne doit jamais passer par le frontend. */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type SystemInfo = {
  app: string;
  environment: string;
  data_mode: "manual" | "demo" | "api";
  database: string;
  providers: { code: string; name: string; kind: string; configured: boolean }[];
};

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}/api/v1${path}`, { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`API ${res.status} sur ${path}`);
  return (await res.json()) as T;
}
