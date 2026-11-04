"use client";

import { useEffect } from "react";

/** Enregistre le service worker uniquement en production (évite les caches gênants en dev). */
export default function ServiceWorkerRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);
  return null;
}
