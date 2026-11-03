# Déploiement

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
