# Fournisseurs de données — conditions vérifiées

Vérification du 2026-11-03 sur les pages officielles (à revérifier avant tout abonnement).

| Fournisseur | Offre gratuite | Notes |
|---|---|---|
| API-Football (api-sports.io) | 100 requêtes/jour | Plan payant suivant : 19 $/mois, 7 500 req/jour. |
| The Odds API | 500 crédits/mois (~16 req/jour) | Pas de cotes historiques en gratuit ; 1 requête = 1 sport × 1 marché × 1 région. |

**Décision étape 4** : les connecteurs restent des squelettes **désactivés** (aucun appel réseau). Les implémenter sans clé reviendrait à livrer du code non testé. Ils seront écrits quand une clé sera disponible, avec : compteur de quota local, cache des réponses, arrêt automatique à l'approche du plafond, marquage `source=api` sur toute donnée importée.

En attendant, la source de données est l'**import CSV** (`POST /api/v1/import/matches`) et la saisie manuelle.

## Format CSV
Colonnes obligatoires : `date, competition, home_team, away_team, home_score, away_score`.
Optionnelles : `season, home_score_ht, away_score_ht` et, pour `home_` / `away_` : `shots, shots_on_target, corners, possession, fouls, yellow, red`.
Dates ISO (`2026-01-10` ou `2026-01-10T20:00:00Z`, UTC par défaut). Séparateur `,` ou `;`. UTF-8, 2 Mo / 5 000 lignes max. Modèle : `frontend/public/modele-matchs.csv`.
