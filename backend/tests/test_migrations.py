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


def test_migrated_database_enforces_append_only(tmp_path):
    """Les déclencheurs posés par la migration 0003 (pas par create_all) bloquent UPDATE/DELETE."""
    import pytest
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import DBAPIError

    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'a.db'}"
    _wipe(url)
    assert _alembic(url, "upgrade", "head").returncode == 0
    e = create_engine(url)
    ts = "2026-01-01 00:00:00"
    with e.begin() as c:
        c.execute(
            text(
                f"INSERT INTO competitions (id, name, source, created_at) VALUES (1,'C','MANUAL','{ts}')"
            )
        )
        for i in (1, 2):
            c.execute(
                text(
                    f"INSERT INTO teams (id, name, source, created_at) VALUES ({i},'T{i}','MANUAL','{ts}')"
                )
            )
        c.execute(
            text(
                f"INSERT INTO matches (id, competition_id, home_team_id, away_team_id, kickoff_at, status, source, created_at) "
                f"VALUES (1,1,1,2,'{ts}','SCHEDULED','MANUAL','{ts}')"
            )
        )
        c.execute(
            text(
                f"INSERT INTO model_versions (id, name, version, is_active, created_at) VALUES (1,'m','1',true,'{ts}')"
            )
        )
        c.execute(
            text(
                f"INSERT INTO predictions (id, match_id, model_version_id, market, selection, probability, created_at) "
                f"VALUES (1,1,1,'1X2','home',0.5,'{ts}')"
            )
        )
    for sql in ("UPDATE predictions SET probability = 0.9", "DELETE FROM predictions"):
        with pytest.raises(DBAPIError), e.begin() as c:
            c.execute(text(sql))
    with pytest.raises(DBAPIError), e.begin() as c:  # unicité du créneau (NULL traité comme -1)
        c.execute(
            text(
                f"INSERT INTO predictions (id, match_id, model_version_id, market, selection, probability, created_at) "
                f"VALUES (2,1,1,'1X2','home',0.6,'{ts}')"
            )
        )
    e.dispose()
    _wipe(url)
