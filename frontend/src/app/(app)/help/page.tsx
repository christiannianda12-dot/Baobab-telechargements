import { PageTitle } from "@/components/ui";

const TERMS: [string, string][] = [
  ["Probabilité du modèle", "La chance estimée par le modèle statistique qu'un résultat se produise (ex. 45 % de victoire à domicile). Ce n'est jamais une certitude."],
  ["Cote (décimale)", "Ce que rapporte une mise de 1 si le pari est gagné, mise comprise. Cote 2,00 : 1 misé → 2 récupérés. Elle correspond à une probabilité « implicite » de 1 ÷ cote (50 % ici)."],
  ["Marge du bookmaker", "Les bookmakers fixent leurs cotes pour toujours gagner un peu : la somme des probabilités implicites dépasse 100 %. L'excédent est leur marge (souvent 3 à 7 %)."],
  ["Valeur espérée (EV)", "Gain moyen par unité misée si nos probabilités sont justes : probabilité × cote − 1. Positive = favorable sur la durée ; négative = perdante. Elle dépend entièrement de la qualité de l'estimation."],
  ["Valeur (badge vert)", "La cote semble plus haute que l'estimation du modèle. Attention : le marché est plus précis que le modèle (voir Fiabilité), donc ce signal est souvent une erreur du modèle."],
  ["Brier / Log Loss", "Deux notes de la qualité d'un ensemble de probabilités : plus c'est bas, mieux c'est. Le hasard pur donne 0,667 (Brier) pour un match à 3 issues."],
  ["Marché (cotes de clôture)", "Les probabilités déduites des cotes moyennes des bookmakers juste avant le match, marge retirée : la référence la plus exigeante."],
  ["Calibration", "Quand le modèle annonce 60 %, l'événement doit arriver environ 60 % du temps. La courbe de la page Fiabilité vérifie cela."],
  ["Combiné", "Plusieurs paris dans un seul : toutes les sélections doivent gagner. Les cotes se multiplient, mais les probabilités aussi (et diminuent vite)."],
  ["Prudent / Équilibré / Ambitieux", "Trois profils de combinés proposés : peu de sélections très probables, un compromis, ou une grosse cote à faible probabilité."],
  ["Prédiction enregistrée", "Avant le match, la prédiction est figée et horodatée : elle ne peut plus être modifiée, et sera comparée au résultat réel (page Historique et Performance)."],
  ["Mise à jour automatique", "Toutes les quelques heures, l'application télécharge les résultats et le calendrier, récupère les cotes, enregistre les prédictions et règle celles des matchs terminés."],
];

export default function Help() {
  return (
    <>
      <PageTitle title="Aide et glossaire" subtitle="Les mots utilisés dans l'application, en langage simple." />
      <div className="card mb-4 text-sm">
        <p className="font-medium">À retenir</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
          <li>L&apos;application <b>analyse</b> : elle ne garantit aucun gain. Sur l&apos;historique testé, les bookmakers sont plus précis que le modèle.</li>
          <li>Les cotes viennent de sources publiques (football-data.co.uk) ou, avec votre clé personnelle, de The Odds API. Vérifiez toujours la cote chez votre bookmaker.</li>
          <li>Les paris sont réglementés selon les pays (âge minimum, licences). Jouez de façon responsable, avec de petites sommes que vous pouvez perdre.</li>
        </ul>
      </div>
      <dl className="space-y-2">{TERMS.map(([t, d]) => (<div key={t} className="card"><dt className="font-medium">{t}</dt><dd className="mt-1 text-sm text-muted">{d}</dd></div>))}</dl>
    </>
  );
}
