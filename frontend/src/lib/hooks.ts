"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { api, ApiError } from "@/lib/api";
import { getToken, setToken, subscribeToken } from "@/lib/session";

export const useToken = () => useSyncExternalStore(subscribeToken, getToken, () => null);

/** GET déclaratif. `path = null` désactive la requête. */
export function useApi<T>(path: string | null) {
  const token = useToken();
  const [nonce, setNonce] = useState(0);
  const [res, setRes] = useState<{ key: string; data?: T; error?: string } | null>(null);
  const key = path ? `${path}|${token}|${nonce}` : null;

  useEffect(() => {
    if (!key || !path) return;
    let cancelled = false;
    api<T>(path)
      .then((data) => !cancelled && setRes({ key, data }))
      .catch((e: Error) => {
        if (e instanceof ApiError && e.status === 401) setToken(null);
        if (!cancelled) setRes({ key, error: e.message });
      });
    return () => {
      cancelled = true;
    };
  }, [key, path]);

  const done = res !== null && res.key === key;
  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data: done ? res.data : undefined, error: done ? res.error : undefined, loading: !!key && !done, reload };
}

/** Début de journée locale + offset (jours), en ISO UTC. */
export function dayStart(offset = 0): string {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + offset);
  return d.toISOString();
}
