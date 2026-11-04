/** Indicateur de session côté navigateur. Le jeton réel vit dans un cookie HttpOnly posé par l'API :
 *  le JavaScript (donc une faille XSS) ne peut pas le lire. Cet indicateur ("1") n'est PAS un secret :
 *  il sert seulement à décider d'afficher l'application ou la page de connexion ; l'API reste seule juge. */
const KEY = "predix_session";
const listeners = new Set<() => void>();

export function getToken(): string | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
export function setToken(flag: string | null) {
  try {
    if (flag) window.localStorage.setItem(KEY, flag);
    else window.localStorage.removeItem(KEY);
  } catch {}
  listeners.forEach((l) => l());
}
export function subscribeToken(cb: () => void) {
  listeners.add(cb);
  return () => void listeners.delete(cb);
}
