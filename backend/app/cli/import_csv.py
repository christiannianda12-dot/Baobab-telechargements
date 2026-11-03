"""Import en ligne de commande d'un ou plusieurs CSV d'historique (format PREDIX ou football-data.co.uk),
puis premier backtest chronologique du modèle sur les données importées.

Usage (depuis backend/, venv activé ; en conteneur : docker compose exec api python -m app.cli.import_csv /imports/*.csv) :
  python -m app.cli.import_csv data/import/*.csv --dry-run          # valide sans écrire
  python -m app.cli.import_csv data/import/*.csv                    # importe puis évalue
  options : --competition "Nom" --season 2024-2025 --no-backtest
"""

import argparse
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionLocal
from app.ml import backtest
from app.ml.data import load_finished
from app.models import Competition
from app.services.csv_import import import_csv


def read(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):  # football-data.co.uk : souvent cp1252
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"{path}: encodage illisible")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--competition")
    ap.add_argument("--season")
    ap.add_argument("--no-backtest", action="store_true")
    a = ap.parse_args()
    bad = 0
    with SessionLocal() as db:
        for f in a.files:
            rep = import_csv(
                db,
                read(f),
                dry_run=a.dry_run,
                max_rows=500_000,
                competition=a.competition,
                season=a.season,
            )
            print(
                f"{f.name} [{rep.source_format}] : {rep.created_matches} match(s), {rep.created_teams} équipe(s), "
                f"{rep.created_competitions} compétition(s), {rep.skipped_duplicates} doublon(s)"
                + (" (simulation)" if a.dry_run else "")
            )
            for e in rep.errors[:15]:
                print(f"   ligne {e['line']} : {e['error']}")
            bad += bool(rep.errors)
        if bad:
            print("\nImport REFUSÉ pour les fichiers en erreur (tout-ou-rien par fichier).")
            return 1
        if a.dry_run or a.no_backtest:
            return 0
        print("\n=== Premier backtest chronologique (modèle de Poisson) ===")
        done: set[str] = set()
        for comp in db.scalars(select(Competition).order_by(Competition.name, Competition.season)):
            key = comp.name.strip().casefold()
            if key in done:
                continue  # toutes les saisons d'un championnat sont évaluées ensemble
            done.add(key)
            recs = load_finished(db, comp.id)
            if len(recs) < 60:
                continue
            seasons = sorted(
                {
                    c.season
                    for c in db.scalars(select(Competition))
                    if c.name.strip().casefold() == key and c.season
                }
            )
            r = backtest.run(recs)
            head = f"- {comp.name} [{', '.join(seasons)}] ({len(recs)} matchs)"
            if "brier" not in r:
                print(f"{head}: {r['note']}")
                continue
            print(
                f"{head}: {r['evaluated']} matchs évalués | Brier {r['brier']:.4f} vs baseline {r['brier_baseline']:.4f} "
                f"(skill {r['brier_skill']:+.1%}) | LogLoss {r['log_loss']:.4f} vs {r['log_loss_baseline']:.4f}"
                + ("" if r["reliable"] else "  [échantillon < 100 : non fiable]")
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
