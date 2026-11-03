# Baobab-telechargements

# PREDIX AI — « Les données avant les pronostics. »

Plateforme d'analyse et de prédiction sportive, **locale d'abord**, sans dépendance à Supabase ni à un service payant.

> **État : étape 2 (base de données et backend).** Aucune prédiction n'est encore produite. Le moteur statistique sera construit à l'étape 5, après validation.

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
| Admin | `GET /admin/users`, `PATCH /admin/users/{id}`, `POST /admin/providers/sync`, `GET /admin/providers` |

Les cotes n'existent que si elles ont été saisies. L'analyse n'applique la correction de marge qu'aux marchés **complets** (1X2, Over/Under, BTTS).

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
