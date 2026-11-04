import io
import os
import subprocess
import sys
from pathlib import Path

from app.services import csv_adapters as ad

ROOT = Path(__file__).resolve().parents[1]
# Échantillon FICTIF reprenant la structure des fichiers football-data.co.uk (équipes et scores inventés pour le test).
FD = (
    "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,HS,AS,HST,AST,HF,AF,HC,AC,HY,AY,HR,AR,B365H,B365D,B365A\n"
    "E0,17/08/2024,15:00,Alpha,Beta,2,1,H,1,0,H,14,9,6,3,10,12,7,4,1,2,0,0,1.9,3.5,4.2\n"
    "E0,24/08/24,,Beta,Gamma,0,0,D,0,0,D,8,,3,,11,9,,5,2,1,0,0,2.1,3.3,3.6\n"
    "E0,18/01/2025,12:30,Gamma,Alpha,1,3,A,0,1,A,10,15,4,8,9,8,3,9,3,0,0,1,4.0,3.6,1.8\n"
    ",,,,,,,,,,,,,,,,,,,,,,,,,\n"
)


def test_sniff_and_conversion():
    assert ad.sniff(FD) == "football-data" and ad.sniff("date,competition,home_team\n") == "native"
    native, fmt = ad.to_native(FD)
    assert fmt == "football-data"
    lines = native.strip().split("\n")
    assert len(lines) == 4  # en-tête + 3 matchs (ligne vide ignorée)
    assert lines[1].startswith(
        "2024-08-17T15:00:00Z,Premier League (Angleterre),2024-2025,Alpha,Beta,2,1"
    )
    assert lines[2].startswith(
        "2024-08-24T12:00:00Z,"
    )  # sans heure : 12:00 UTC ; année sur 2 chiffres
    assert lines[3].split(",")[2] == "2024-2025"  # janvier 2025 appartient à la saison 2024-2025


def test_override_and_missing_values_stay_empty():
    native, _ = ad.to_native(FD, competition="Ma Ligue", season="2099")
    assert native.splitlines()[1].split(",")[1:3] == ["Ma Ligue", "2099"]
    row2 = native.splitlines()[2].split(",")
    head = native.splitlines()[0].split(",")
    assert (
        row2[head.index("away_shots")] == "" and row2[head.index("home_corners")] == ""
    )  # jamais 0 par défaut


def test_api_imports_football_data_format_idempotently(client, auth_headers):
    def post():
        return client.post(
            "/api/v1/import/matches",
            headers=auth_headers,
            files={"file": ("e0.csv", io.BytesIO(FD.encode()), "text/csv")},
        )

    r = post().json()
    assert (
        r["source_format"] == "football-data"
        and r["created_matches"] == 3
        and r["created_teams"] == 3
    )
    assert post().json()["skipped_duplicates"] == 3
    stats = client.get("/api/v1/matches/1/statistics").json()
    assert {s["shots"] for s in stats} == {14, 9} and any(s["corners"] == 7 for s in stats)


def test_cli_dry_run_and_import(tmp_path):
    f = tmp_path / "e0.csv"
    f.write_bytes(
        FD.replace("Alpha", "Équipe Ça").encode("cp1252")
    )  # encodage historique de la source
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'c.db'}"}

    def sh(*a):
        return subprocess.run(
            [sys.executable, *a], cwd=ROOT, env=env, capture_output=True, text=True
        )

    assert sh("-m", "alembic", "upgrade", "head").returncode == 0
    dry = sh("../scripts/import_csv.py", str(f), "--dry-run")
    assert dry.returncode == 0 and "3 match(s)" in dry.stdout and "simulation" in dry.stdout
    real = sh("../scripts/import_csv.py", str(f))
    assert real.returncode == 0 and "Premier backtest" in real.stdout, real.stderr
    again = sh("../scripts/import_csv.py", str(f), "--no-backtest")
    assert "3 doublon(s)" in again.stdout


def test_accented_names_are_matched_case_insensitively(client, auth_headers):
    """Régression : lower() de SQLite ne gère pas les accents => équipes recréées à chaque import."""
    csv = "date,competition,home_team,away_team,home_score,away_score\n2026-01-01,L,Atlético Madrid,1. FC Köln,1,0\n"

    def up(t):
        files = {"file": ("a.csv", io.BytesIO(t.encode()), "text/csv")}
        return client.post("/api/v1/import/matches", headers=auth_headers, files=files).json()

    assert up(csv)["created_teams"] == 2
    again = up(
        csv.replace("Atlético Madrid", "ATLÉTICO MADRID").replace("2026-01-01", "2026-02-01")
    )
    assert again["created_teams"] == 0 and again["created_matches"] == 1
