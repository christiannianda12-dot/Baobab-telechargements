import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(args, db_url):
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, *args], cwd=ROOT, env=env, capture_output=True, text=True
    )


def test_backup_is_restorable_and_rotated(tmp_path):
    db = tmp_path / "live.db"
    url = f"sqlite:///{db}"
    assert (
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env={**os.environ, "DATABASE_URL": url},
            capture_output=True,
        ).returncode
        == 0
    )
    with sqlite3.connect(db) as c:
        c.execute(
            "INSERT INTO teams (name, source, created_at) VALUES ('Sauvegardée','MANUAL','2026-01-01 00:00:00')"
        )
    for _ in range(3):
        r = _run(["../scripts/backup_db.py", "--keep", "2"], url)
        assert r.returncode == 0, r.stderr
    backups = sorted((tmp_path / "backups").glob("predix-*.db"))
    assert len(backups) == 2  # rotation
    with sqlite3.connect(
        backups[-1]
    ) as c:  # restauration : la copie s'ouvre et contient les données
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("SELECT name FROM teams").fetchone()[0] == "Sauvegardée"
