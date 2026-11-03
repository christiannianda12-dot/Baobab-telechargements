# Baobab-telechargements

# PREDIX AI — « Les données avant les pronostics. »

Plateforme d'analyse et de prédiction sportive, **locale d'abord**, sans dépendance à Supabase ni à un service payant.

> **État : les 8 étapes du plan sont réalisées.** Évolutions restantes (dépendent d'éléments extérieurs) : modèles avancés (historique réel), connecteurs API (clés), connecteur LLM (clé). Aucune prédiction n'est encore produite. Le moteur statistique sera construit à l'étape 5, après validation.

## Stack

| Couche | Technologie |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, PWA |
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Base de données | SQLite (dev) → PostgreSQL (prod) via SQLAlchemy 2 |
| Migrations | Alembic (mode batch, compatible SQLite et PostgreSQL) |
| Sécurité | bcrypt, JWT (PyJWT), limiteur de requêtes, CORS restreint |
| Tests | pytest, ruff, ESLint, tsc |

## Prérequis

Python ≥ 3.11, Node ≥ 20, npm. Aucun compte externe requis.

## Installation

```bash
cp .env.example .env            # puis éditer SECRET_KEY
make install                    # ou voir « Sans make » ci-dessous
make migrate                    # crée backend/data/predix.db
cp frontend/.env.example frontend/.env.local
```

## Démarrage

```bash
make api    # http://localhost:8000  (docs interactives : /docs)
make web    # http://localhost:3000
```

Le premier compte créé via `POST /api/v1/auth/register` devient administrateur.

## Tests

```bash
make test   # backend (pytest) + frontend (eslint + tsc)
make lint   # ruff
```

## Sans make

```bash
cd backend && python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt && alembic upgrade head
uvicorn app.main:app --reload --port 8000
# autre terminal
cd frontend && npm install && npm run dev
```

## API disponible (`/docs` pour le détail)

| Domaine | Routes |
|---|---|
| Système | `GET /health`, `GET /system/info` |
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Données (écriture : connecté) | `/teams`, `/competitions`, `/matches` (+ `PATCH` résultat) |
| Statistiques | `GET /matches/{id}/statistics`, `PUT /matches/{id}/statistics/{team_id}` |
| Cotes | `POST/GET /matches/{id}/odds`, `GET /matches/{id}/odds/analysis`, `POST /odds/calculate` |
| Import et analyse | `POST /import/matches` (CSV, `dry_run`), `GET /matches/{id}/analysis` (forme, domicile/extérieur, confrontations directes) |
| Moteur | `GET /matches/{id}/prediction`, `GET /competitions/{id}/elo`, `GET /competitions/{id}/backtest` |
| Historique | `POST /matches/{id}/predictions` (enregistrement immuable), `GET /predictions`, `POST /predictions/settle`, `GET /performance` |
| Assistant et combinés | `POST /assistant/chat`, `GET /assistant/status`, `POST /combos/analyze`, `POST /combos/suggest` |
| Admin | `GET /admin/users`, `PATCH /admin/users/{id}`, `POST /admin/providers/sync`, `GET /admin/providers` |

Les cotes n'existent que si elles ont été saisies. L'analyse n'applique la correction de marge qu'aux marchés **complets** (1X2, Over/Under, BTTS).

## Importer votre historique réel

`python ../scripts/import_csv.py data/import/*.csv` (depuis `backend/`) : accepte le format PREDIX et celui de football-data.co.uk, valide tout avant d'écrire, puis affiche le **premier backtest réel** du modèle (Brier / Log Loss contre la baseline). Détails dans [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Sécurité et déploiement

Cookie de session `HttpOnly`, protection CSRF, en-têtes de sécurité, configuration de production stricte, audit des dépendances, conteneurs non-root, sauvegardes testées. Détail et **limites connues** : [`docs/SECURITY.md`](docs/SECURITY.md). Déploiement (`docker compose`, HTTPS, sauvegardes, CI) : [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Assistant et combinés

- **Assistant en mode règles** : il détecte l'intention (analyse d'un match, comparaison de deux équipes, marchés les plus probables / à valeur, combiné), interroge les données et le moteur, et rédige sa réponse **uniquement** à partir de ces résultats. Équipe inconnue, match absent ou historique insuffisant : il le dit au lieu de répondre.
- **Aucun modèle de langage n'est connecté** et l'interface l'affiche. L'architecture (`backend/app/assistant/llm.py`) prévoit un connecteur (Claude, GPT…) qui ne ferait que *reformuler* une réponse déjà calculée ; sans connecteur implémenté, `LLM_API_KEY` est ignorée.
- **Combinés** : probabilité conjointe **exacte** (matrice de scores) pour plusieurs sélections d'un même match, produit pour des matchs différents (hypothèse d'indépendance annoncée) ; sélections incompatibles refusées ; avertissements (> 4 jambes, < 10 %, historique court, cote totale non applicable aux sélections corrélées). La « suggestion » privilégie la **probabilité**, pas la valeur, et le dit.

## Historique vérifiable et performance

- **Enregistrement** : une prédiction (1X2, plus/moins 2,5, BTTS) ne peut être enregistrée qu'**avant le coup d'envoi**, **une seule fois** par match et par version de modèle, avec la meilleure cote saisie à cet instant.
- **Immuabilité garantie par la base** : des déclencheurs SQL (SQLite et PostgreSQL) refusent tout `UPDATE`/`DELETE` sur `predictions` et `prediction_results`, même en SQL brut. Une contrainte d'unicité empêche les doublons.
- **Règlement automatique** quand un match passe à « terminé » (ou « annulé » : issues annulées, exclues des statistiques) ; idempotent.
- **Performance** : taux de réussite (intervalle de Wilson 95 %), Brier Score, Log Loss, ROI théorique (issue favorite avec cote saisie) et ROI des paris à valeur positive, par marché et par championnat. Chaque tableau signale « peu fiable » sous 100 événements réglés.

## Moteur statistique (palier 1)

- **Poisson** (attaque/défense par équipe, avantage du terrain, rétrécissement vers la moyenne, pondération temporelle) : 1X2, double chance, plus/moins 0,5 à 4,5, les deux équipes marquent, scores indicatifs.
- **Refus de prédire** sous 30 matchs d'historique dans la compétition ou 5 matchs par équipe : l'écran affiche la raison, jamais une probabilité inventée.
- **Valeur espérée** calculée uniquement sur les cotes que vous avez saisies.
- **Elo** : classement de force relative (les probabilités viennent de Poisson).
- **Backtest chronologique** : chaque match est prédit avec les seuls matchs antérieurs ; Brier, Log Loss, comparés à une baseline (fréquences passées) et table de calibration. En dessous de 100 matchs évalués, le résultat est signalé comme non fiable.
- Les tests utilisent des ligues **synthétiques** (générées en mémoire, jamais insérées dans l'application) pour vérifier que le code retrouve des forces connues. Cela valide l'implémentation, **pas** la performance sur du sport réel : seul un backtest sur vos données réelles le fait.

## Données sportives

- **Import CSV** (Administration ou API) : tout-ou-rien, erreurs localisées par ligne, doublons ignorés, cellule vide = donnée absente. Format et modèle : [`docs/PROVIDERS.md`](docs/PROVIDERS.md).
- **Forme des équipes** calculée à la demande sur les seuls matchs terminés *antérieurs* au coup d'envoi (pas de fuite du futur) ; moyennes de corners/tirs/possession/cartons sur les seuls matchs où la donnée existe (« 2/3 » = 2 matchs sur 3). Avertissement sous 5 matchs.
- **API externes** : conditions vérifiées, connecteurs volontairement non implémentés sans clé (voir `docs/PROVIDERS.md`).

## Interface (12 pages)

Connexion, inscription, tableau de bord, matchs du jour, calendrier, détail d'un match (statistiques, cotes saisies, marge), saisie des cotes et résultats, paramètres, administration (utilisateurs + saisie manuelle). **Assistant, combinés, historique et performance** affichent « Non disponible » avec l'étape prévue : aucune donnée simulée. Navigation latérale sur ordinateur, barre inférieure sur téléphone.

Test de bout en bout : voir `scripts/e2e_smoke.js` (7 scénarios : redirections, inscription, saisie manuelle, cotes, déconnexion).

## Tests PostgreSQL

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/predix_test make test-pg
```

## Sauvegarde

`make backup` crée une copie horodatée cohérente de la base SQLite dans `backend/data/backups/` (14 conservées).

## Modes de données (`DATA_MODE`)

- `manual` (défaut) : saisie manuelle des équipes, compétitions, matchs, cotes. Aucune API externe.
- `demo` : données fictives, **toujours** marquées `source=demo` et jamais présentées comme réelles (non encore implémenté).
- `api` : fournisseurs externes. Chaque connecteur reste **désactivé tant que sa clé est vide** ; aucun appel réseau n'est émis sans clé.

## Documentation

Architecture, arborescence, risques et feuille de route : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

Avertissement : les probabilités sont des estimations statistiques, jamais des garanties. Pariez de façon responsable.
