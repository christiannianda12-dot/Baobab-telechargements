"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { api, ApiError } from "@/lib/api";
import { getToken, setToken, subscribeToken } from "@/lib/session";

export const useToken = () => useSyncExternalStore(subscribeToken, getToken, () => null);

/** GET déclaratif. `path = null` désactive la requête. `refreshMs` : rafraîchissement automatique silencieux
 *  (les données restent affichées pendant la mise à jour ; pause quand l'onglet est caché). */
export function useApi<T>(path: string | null, opts?: { refreshMs?: number }) {
  const token = useToken();
  const [nonce, setNonce] = useState(0);
  const [res, setRes] = useState<{ path: string; token: string | null; at: number; data?: T; error?: string } | null>(null);
  const refreshMs = opts?.refreshMs;

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    api<T>(path)
      .then((data) => !cancelled && setRes({ path, token, at: Date.now(), data }))
      .catch((e: Error) => {
        if (e instanceof ApiError && e.status === 401) setToken(null);
        if (!cancelled) setRes((prev) => ({ path, token, at: Date.now(), data: prev?.path === path ? prev.data : undefined, error: e.message }));
      });
    return () => {
      cancelled = true;
    };
  }, [path, token, nonce]);

  useEffect(() => {
    if (!refreshMs || !path) return;
    const t = setInterval(() => { if (document.visibilityState === "visible") setNonce((n) => n + 1); }, refreshMs);
    return () => clearInterval(t);
  }, [refreshMs, path]);

  const fresh = res !== null && res.path === path && res.token === token;
  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data: fresh ? res.data : undefined, error: fresh ? res.error : undefined, loading: !!path && !fresh, reload, updatedAt: fresh ? res.at : null };
}

/** Début de journée locale + offset (jours), en ISO UTC. */
export function dayStart(offset = 0): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + offset);
  return d.toISOString();
}
