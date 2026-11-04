"use client";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 text-center">
      <h1 className="text-2xl font-semibold">Une erreur est survenue</h1>
      <p className="mt-2 text-sm text-muted">Vos données ne sont pas affectées. Réessayez ; si le problème persiste, rechargez la page ou redémarrez l&apos;application.</p>
      <p className="mt-2 break-words font-mono text-xs text-muted">{error.message}</p>
      <button className="btn mx-auto mt-4" onClick={reset}>Réessayer</button>
    </main>
  );
}
