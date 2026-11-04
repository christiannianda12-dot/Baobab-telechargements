# Déploiement

## Mise en ligne sur votre serveur (recommandé) — site + application installable
Prérequis : un serveur Linux (VPS) avec Docker + Docker Compose, un **nom de domaine** dont l'enregistrement DNS `A` pointe vers le serveur, ports **80 et 443** ouverts.
```bash
git clone <votre dépôt> predix && cd predix && git checkout claude/predix-ai-setup-tlx60r
cp .env.example .env     # renseigner : DOMAIN, POSTGRES_PASSWORD (fort), SECRET_KEY (>= 32 car.)
./scripts/deploy.sh      # construit, démarre, attend la santé de l'API
```
- **Caddy** obtient et renouvelle automatiquement le certificat HTTPS. Le site et l'API partagent la même adresse (`https://DOMAIN` et `https://DOMAIN/api/...`).
- Seuls 80/443 sont exposés ; base et API restent sur le réseau interne.
- **Sauvegarde PostgreSQL automatique** toutes les 24 h dans `./backups` (14 jours conservés, `BACKUP_KEEP_DAYS`). Copiez ce dossier hors du serveur.
- Mise à jour : `git pull && ./scripts/deploy.sh`.
- **Application sur téléphone** : ouvrir `https://DOMAIN` dans Chrome/Safari puis « Ajouter à l'écran d'accueil » (PWA : plein écran, icône, page hors ligne).
- Importer l'historique réel : voir ci-dessous « Importer un historique ».

## Importer un historique (CSV)
Formats acceptés : format PREDIX (`frontend/public/modele-matchs.csv`) et **football-data.co.uk** (détecté automatiquement ; compétition déduite de `Div`, saison de la date).
```bash
cd backend && . .venv/bin/activate && alembic upgrade head
python ../scripts/import_csv.py data/import/*.csv --dry-run   # valide sans écrire
python ../scripts/import_csv.py data/import/*.csv             # importe puis affiche le premier backtest réel
```
En production : déposez vos CSV dans `./imports/` sur le serveur puis `docker compose -f docker-compose.prod.yml exec api python -m app.cli.import_csv /imports/*.csv` (ajoutez `--dry-run` pour valider d'abord). Ou via **Administration > Import CSV** (5 000 lignes max par fichier dans l'interface ; la ligne de commande n'a pas cette limite).

## Essai local (conteneurs)
```bash
cp .env.example .env     # renseigner POSTGRES_PASSWORD, SECRET_KEY (>= 32 car.), CORS_ORIGINS=http://localhost:3000
# pour un essai en HTTP uniquement : ENVIRONMENT=development et COOKIE_SECURE=false
docker compose up --build
```
API : http://localhost:8000 · Web : http://localhost:3000. Les migrations s'appliquent au démarrage de l'API ; les données sont dans le volume `pgdata`.
Générer un secret : `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Production (checklist)
1. **HTTPS obligatoire** (le cookie est `Secure`) : reverse proxy (Caddy, Nginx, Traefik) devant `web` et `api`, **sur le même domaine ou des sous-domaines du même site** (ex. `app.exemple.com` et `api.exemple.com`).
2. `.env` : `ENVIRONMENT=production`, `SECRET_KEY` fort, `CORS_ORIGINS=https://app.exemple.com`, `NEXT_PUBLIC_API_URL=https://api.exemple.com` (figé au build du frontend), `TRUST_PROXY_HEADERS=true` si le proxy pose `X-Forwarded-For`.
3. Ne pas publier les ports 5432 (base) ; n'exposer que le proxy.
4. Sauvegardes planifiées : `scripts/backup_pg.sh` (cron quotidien) vers un stockage distinct ; **tester une restauration** (`pg_restore`).
5. Premier compte créé = administrateur : le créer immédiatement, avant toute exposition publique.
6. Surveiller `GET /api/v1/health`.
7. Relire `docs/SECURITY.md` (limites connues).

## Hébergement
Compatible avec tout hébergeur de conteneurs ou VM supportant Docker + PostgreSQL. Aucune dépendance à un fournisseur (ni Supabase) : la base est sélectionnée par `DATABASE_URL`.

## Application mobile
La PWA (manifeste + service worker + icônes 192/512) est installable depuis le navigateur du téléphone en HTTPS. L'API REST et l'authentification Bearer permettent de brancher plus tard une application native (React Native/Flutter) sans changer le backend.

## Intégration continue
`.github/workflows/ci.yml` : lint, tests SQLite **et** PostgreSQL, audit pip, lint/types/build frontend, audit npm.
