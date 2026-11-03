import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _alembic(db_url, *args):
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True
    )


def test_migrations_apply_roundtrip_and_match_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    for args in (("upgrade", "head"), ("check",), ("downgrade", "base"), ("upgrade", "head")):
        r = _alembic(url, *args)
        assert r.returncode == 0, r.stderr
