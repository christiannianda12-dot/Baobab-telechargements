import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 text-center">
      <h1 className="text-2xl font-semibold">Page introuvable</h1>
      <p className="mt-2 text-sm text-muted">Cette adresse n&apos;existe pas.</p>
      <Link href="/dashboard" className="btn mx-auto mt-4">Retour au tableau de bord</Link>
    </main>
  );
}
