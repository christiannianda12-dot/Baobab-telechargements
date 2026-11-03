export const metadata = { title: "Hors ligne" };

export default function Offline() {
  return (
    <main className="mx-auto max-w-md flex-1 px-4 py-20 text-center">
      <h1 className="text-2xl font-semibold">Vous êtes hors ligne</h1>
      <p className="mt-3 text-muted">Reconnectez-vous pour consulter les données à jour.</p>
    </main>
  );
}
