@echo off
chcp 65001 >nul
cd /d "%~dp0"
docker compose --env-file .env.local -f docker-compose.local.yml exec -T api python -m app.cli.backup
if not exist sauvegardes mkdir sauvegardes
docker compose --env-file .env.local -f docker-compose.local.yml cp api:/app/data/backups/. sauvegardes
echo Sauvegardes copiees dans le dossier "sauvegardes". Copiez-le aussi sur une cle USB ou un autre disque.
pause
