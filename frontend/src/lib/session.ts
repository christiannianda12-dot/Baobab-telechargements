/** Jeton de session (localStorage + store réactif). Compromis assumé en local ; en production,
 *  préférer un cookie httpOnly émis par le backend. */
const KEY = "predix_token";
const listeners = new Set<() => void>();

export function getToken(): string | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
export function setToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(KEY, token);
    else window.localStorage.removeItem(KEY);
  } catch {}
  listeners.forEach((l) => l());
}
export function subscribeToken(cb: () => void) {
  listeners.add(cb);
  return () => void listeners.delete(cb);
}
