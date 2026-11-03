@echo off
chcp 65001 >nul
cd /d "%~dp0"
docker compose --env-file .env.local -f docker-compose.local.yml stop
echo PREDIX AI est arrete. Vos donnees sont conservees.
pause
