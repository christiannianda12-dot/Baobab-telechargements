"""Sauvegarde horodatée de la base SQLite (API de backup native : sûre même base en cours d'usage).

Usage : cd backend && python ../scripts/backup_db.py [--keep 14]
Pour PostgreSQL (production), utiliser pg_dump / les sauvegardes du fournisseur.
"""
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, default=14, help="nombre de sauvegardes conservées")
    keep = ap.parse_args().keep
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        print("Sauvegarde automatique prévue pour SQLite uniquement.", file=sys.stderr)
        return 1
    src = Path(url.removeprefix("sqlite:///"))
    src = src if src.is_absolute() else (ROOT / src)
    if not src.exists():
        print(f"Base introuvable : {src}", file=sys.stderr)
        return 1
    dest_dir = src.parent / "backups"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / f"predix-{datetime.now():%Y%m%d-%H%M%S-%f}.db"
    with sqlite3.connect(src) as s, sqlite3.connect(dest) as d:
        s.backup(d)
    for old in sorted(dest_dir.glob("predix-*.db"))[:-keep]:
        old.unlink()
    print(f"Sauvegarde créée : {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
