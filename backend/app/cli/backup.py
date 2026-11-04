"""Sauvegarde cohérente de la base SQLite (API de backup native, sûre même base en cours d'usage).

Usage : python -m app.cli.backup [--keep 14]   (écrit dans <dossier de la base>/backups/)"""

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, default=14)
    keep = ap.parse_args().keep
    url = get_settings().database_url
    if not url.startswith("sqlite:///"):
        print("Sauvegarde automatique prévue pour SQLite uniquement.")
        return 1
    src = Path(url.removeprefix("sqlite:///"))
    if not src.exists():
        print(f"Base introuvable : {src}")
        return 1
    dest_dir = src.parent / "backups"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / f"predix-{datetime.now():%Y%m%d-%H%M%S}.db"
    with sqlite3.connect(src) as s, sqlite3.connect(dest) as d:
        s.backup(d)
    for old in sorted(dest_dir.glob("predix-*.db"))[:-keep]:
        old.unlink()
    print(f"Sauvegarde créée : {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
