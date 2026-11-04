@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PREDIX AI
echo.
echo === PREDIX AI - demarrage ===
docker --version >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop n est pas installe. Installez-le puis relancez ce fichier.
  start https://www.docker.com/products/docker-desktop/
  pause
  exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop est installe mais pas demarre. Ouvrez-le, attendez qu il soit pret, puis relancez ce fichier.
  pause
  exit /b 1
)
if not exist .env.local (
  echo Creation de la cle secrete locale...
  powershell -NoProfile -ExecutionPolicy Bypass -File deploy\secret.ps1 > .env.local
)
echo Construction et demarrage (la premiere fois : 5 a 15 minutes, soyez patient)...
docker compose --env-file .env.local -f docker-compose.local.yml up -d --build
if errorlevel 1 (
  echo ERREUR au demarrage. Verifiez votre connexion Internet puis relancez.
  pause
  exit /b 1
)
echo Attente du demarrage...
set /a n=0
:wait
curl -s http://localhost:3000/api/v1/health >nul 2>&1 && goto ready
set /a n+=1
if %n% GEQ 40 goto timeout
timeout /t 3 /nobreak >nul
goto wait
:ready
echo.
echo === PREDIX AI est pret ===
echo Sur cet ordinateur : http://localhost:3000
echo Sur le telephone (meme Wi-Fi) : http://VOTRE-IP:3000   (votre IP IPv4 ci-dessous)
ipconfig | findstr /c:"IPv4"
start http://localhost:3000
pause
exit /b 0
:timeout
echo Le demarrage prend trop de temps. Consultez : docker compose -f docker-compose.local.yml logs
pause
