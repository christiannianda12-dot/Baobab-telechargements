import ApiStatus from "@/components/ApiStatus";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-10 sm:py-16">
      <p className="font-mono text-sm tracking-widest text-accent">PREDIX AI</p>
      <h1 className="mt-2 text-3xl font-semibold sm:text-4xl">Les données avant les pronostics.</h1>
      <p className="mt-3 text-muted">
        Fondations techniques — étape 1. Aucune prédiction n&apos;est encore produite : le moteur
        statistique n&apos;est pas construit.
      </p>
      <section aria-labelledby="status" className="mt-8 rounded-xl border border-border bg-surface p-5">
        <h2 id="status" className="mb-4 text-lg font-medium">
          État du système
        </h2>
        <ApiStatus />
      </section>
    </main>
  );
}
