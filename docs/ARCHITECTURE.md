# Architecture PREDIX AI

## Principes
1. Local d'abord, zéro abonnement. 2. Indépendance des fournisseurs (DB, API, LLM). 3. Aucune donnée inventée : une valeur absente reste `NULL`. 4. Provenance explicite de chaque donnée (`manual` / `demo` / `api`). 5. Prédictions immuables et horodatées.

## Arborescence

```
.
├── .env.example               # configuration (copier vers .env, jamais committé)
├── Makefile                   # commandes de développement
├── scripts/backup_db.py       # sauvegarde SQLite
├── docs/ARCHITECTURE.md
├── backend/
│   ├── alembic.ini
│   ├── migrations/            # env.py + versions/0001 (schéma initial, 12 tables)
│   ├── data/                  # predix.db (ignoré par git)
│   ├── app/
│   │   ├── main.py            # fabrique FastAPI, CORS
│   │   ├── core/              # config (env), security (bcrypt/JWT), rate_limit
│   │   ├── db/                # Base (conventions de nommage), session/engine
│   │   ├── models/            # user, sports, odds, prediction, provider
│   │   ├── schemas/           # contrats Pydantic (validation d'entrée/sortie)
│   │   ├── api/               # deps.py (auth) + v1/{health,auth,sports,router}
│   │   ├── providers/         # connecteurs API-Football / The Odds API (squelettes)
│   │   └── services/          # (réservé) logique métier : analyse, cotes, perf
│   └── tests/                 # pytest : santé, auth, sports, modèles, migrations
└── frontend/
    ├── src/app/               # layout, page d'accueil, /offline, manifest PWA
    ├── src/components/        # ApiStatus, ServiceWorkerRegister
    ├── src/lib/api.ts         # client API
    └── public/                # sw.js, icônes PWA
```

À venir (étapes suivantes) : `backend/app/ml/` (Poisson, Elo, régression logistique, XGBoost, calibration), `backend/app/services/` (cotes, combinés, performance), `backend/app/assistant/` (interface LLM débranchée par défaut), pages frontend.

## Modèle de données (12 tables)
`users`, `teams`, `competitions`, `matches`, `match_statistics`, `team_forms`, `odds`, `predictions`, `prediction_results`, `analysis_history`, `api_providers`, `model_versions`.
- Clés étrangères appliquées (SQLite : `PRAGMA foreign_keys=ON`).
- `predictions` : toute mise à jour est refusée par une garde ORM. **Limite connue** : la garde ne couvre pas le SQL brut ; un trigger SQL (SQLite + PostgreSQL) sera ajouté à l'étape 7, avec la règle « aucune création après le coup d'envoi ».
- Les clés API ne sont jamais stockées en base (variables d'environnement uniquement).

## Portabilité PostgreSQL
SQLAlchemy 2 + Alembic en mode batch + conventions de nommage des contraintes. Passage : installer `psycopg[binary]`, changer `DATABASE_URL`, relancer `alembic upgrade head`. À valider par des tests sur un vrai PostgreSQL avant la production (non testé à ce stade).

## Sécurité (état actuel)
bcrypt, JWT signé (HS256) à expiration, `SECRET_KEY` obligatoire ≥ 32 car. en production, limitation de débit sur login/inscription (en mémoire : instance unique), CORS restreint, docs API masquées en production, temps de réponse égalisé sur login. **À faire** : révocation/rafraîchissement de jetons, limiteur partagé (Redis) en production, en-têtes de sécurité côté reverse proxy.

## Risques techniques
| Risque | Mitigation |
|---|---|
| Qualité/volume des données insuffisants pour XGBoost | Commencer par Poisson/Elo ; XGBoost seulement au-delà d'un seuil d'échantillons ; afficher les limites |
| Coûts/quotas des API sportives | Connecteurs désactivés sans clé ; vérifier les conditions avant intégration |
| Biais de rétro-évaluation (fuite de données) | Évaluation chronologique stricte, prédictions immuables |
| Corrélations dans les combinés | Pas de produit naïf des probabilités ; estimation conjointe explicite |
| Divergences SQLite/PostgreSQL | Tests de migration ; CI PostgreSQL à prévoir |
| Dépendances (Next gabarit pointait une version non publiée) | Versions fixées ; lockfile committé |

## Feuille de route
1. ✅ Architecture et environnement local
2. Base de données et backend complets (cotes, stats, utilisateurs/admin, seed manuel)
3. Interface et tableau de bord (12 pages, navigation mobile)
4. Gestion des données sportives (import manuel/CSV, connecteurs réels avec clés)
5. Moteur statistique et prédictif
6. Assistant conversationnel (interface LLM débranchée par défaut)
7. Historique et évaluation (Brier, Log Loss, ROI)
8. Tests, sécurisation, déploiement
