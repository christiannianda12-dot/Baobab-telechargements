#!/usr/bin/env sh
# Déploiement / mise à jour en production : ./scripts/deploy.sh
set -eu
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Fichier .env absent : cp .env.example .env puis renseigner DOMAIN, POSTGRES_PASSWORD, SECRET_KEY"; exit 1; }
set -a; . ./.env; set +a
for v in DOMAIN POSTGRES_PASSWORD SECRET_KEY; do
  eval "val=\${$v:-}"
  [ -n "$val" ] || { echo "$v manquant dans .env"; exit 1; }
done
[ "${#SECRET_KEY}" -ge 32 ] || { echo "SECRET_KEY trop court (>= 32 caractères)"; exit 1; }
[ "$POSTGRES_PASSWORD" != "change-me" ] || { echo "Changez POSTGRES_PASSWORD (valeur d'exemple)"; exit 1; }
docker compose -f docker-compose.prod.yml up -d --build
echo "Attente de l'API…"
i=0
until docker compose -f docker-compose.prod.yml exec -T api python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')" >/dev/null 2>&1; do
  i=$((i + 1))
  [ "$i" -lt 40 ] || { echo "L'API ne répond pas : docker compose -f docker-compose.prod.yml logs api"; exit 1; }
  sleep 3
done
echo "OK : https://$DOMAIN  (le premier compte créé devient administrateur : créez-le maintenant)"
