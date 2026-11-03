#!/usr/bin/env sh
# Sauvegarde PostgreSQL (format custom, compressé). Usage : DATABASE_URL_PG=postgresql://user:pass@host/db ./scripts/backup_pg.sh [dossier] [garder]
# Restauration : pg_restore --clean --if-exists -d <url> <fichier>
set -eu
: "${DATABASE_URL_PG:?définir DATABASE_URL_PG (URL libpq, sans +psycopg)}"
dir="${1:-backups}"; keep="${2:-14}"
mkdir -p "$dir"
out="$dir/predix-$(date +%Y%m%d-%H%M%S).dump"
pg_dump --format=custom --file="$out" "$DATABASE_URL_PG"
ls -1t "$dir"/predix-*.dump | tail -n +"$((keep + 1))" | xargs -r rm --
echo "Sauvegarde créée : $out"
