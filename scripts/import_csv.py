"""Enveloppe : python ../scripts/import_csv.py <fichiers> (voir app/cli/import_csv.py pour les options)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.cli.import_csv import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
