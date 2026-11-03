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


def _wipe(url):
    """Repart d'une base vide (toutes tables, y compris alembic_version)."""
    from sqlalchemy import MetaData, create_engine

    engine = create_engine(url)
    meta = MetaData()
    meta.reflect(engine)
    meta.drop_all(engine)
    engine.dispose()


def test_migrations_apply_roundtrip_and_match_models(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'm.db'}"
    _wipe(url)
    for args in (("upgrade", "head"), ("check",), ("downgrade", "base"), ("upgrade", "head")):
        r = _alembic(url, *args)
        assert r.returncode == 0, r.stderr
        # état final propre pour les tests suivants
    _wipe(url)
