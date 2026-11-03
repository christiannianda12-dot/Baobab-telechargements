#!/usr/bin/env sh
# Mac / Linux : ./demarrer.sh   (équivalent de Demarrer-PREDIX.bat)
set -eu
cd "$(dirname "$0")"
command -v docker >/dev/null || { echo "Installez Docker Desktop : https://www.docker.com/products/docker-desktop/"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker est installé mais pas démarré : ouvrez-le puis relancez."; exit 1; }
[ -f .env.local ] || echo "SECRET_KEY=$(openssl rand -hex 32)" > .env.local
docker compose --env-file .env.local -f docker-compose.local.yml up -d --build
i=0; until curl -s http://localhost:3000/api/v1/health >/dev/null 2>&1; do i=$((i+1)); [ "$i" -lt 40 ] || { echo "Démarrage trop long : docker compose -f docker-compose.local.yml logs"; exit 1; }; sleep 3; done
echo "PREDIX AI est prêt : http://localhost:3000"
echo "Depuis le téléphone (même Wi-Fi) : http://<IP de ce PC>:3000"
