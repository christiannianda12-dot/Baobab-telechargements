import math
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.ml import poisson
from app.models.prediction import PredictionOutcome
from app.services import tracking
from tests.synth import league
from tests.test_prediction_api import _load


@pytest.fixture
def setup(client, db_session, auth_headers, monkeypatch):
    recs, _ = league()
    cid, mid = _load(db_session, recs, upto=200)
    from app.models import Match

    kick = db_session.get(Match, mid).kickoff_at
    monkeypatch.setattr(tracking, "utcnow", lambda: kick - timedelta(days=1))
    return client, auth_headers, cid, mid, db_session


def _record(c, h, mid):
    return c.post(f"/api/v1/matches/{mid}/predictions", headers=h)


def test_record_requires_auth_and_is_idempotent(setup):
    c, h, _, mid, db = setup
    assert c.post(f"/api/v1/matches/{mid}/predictions").status_code == 401
    r = _record(c, h, mid)
    assert r.status_code == 201 and r.json() == {
        "match_id": mid,
        "already_recorded": False,
        "count": 7,
    }
    r2 = _record(c, h, mid)
    assert r2.json()["already_recorded"] is True and r2.json()["count"] == 7
    rows = c.get(f"/api/v1/predictions?match_id={mid}").json()
    assert len(rows) == 7 and all(x["outcome"] is None for x in rows)
    p1x2 = [x["probability"] for x in rows if x["market"] == "1X2"]
    assert (
        sum(p1x2) == pytest.approx(1.0) and rows[0]["model"] == f"poisson-{poisson.MODEL_VERSION}"
    )


def test_record_rejected_after_kickoff_and_without_history(setup, monkeypatch):
    c, h, _, mid, db = setup
    from app.models import Match

    kick = db.get(Match, mid).kickoff_at
    monkeypatch.setattr(tracking, "utcnow", lambda: kick)
    r = _record(c, h, mid)
    assert r.status_code == 409 and "commencé" in r.json()["detail"]
    assert c.get(f"/api/v1/predictions?match_id={mid}").json() == []


def test_record_refused_when_model_unavailable(client, db_session, auth_headers, monkeypatch):
    recs, _ = league()
    _, mid = _load(db_session, recs, upto=10)
    monkeypatch.setattr(tracking, "utcnow", lambda: recs[0].when)
    r = client.post(f"/api/v1/matches/{mid}/predictions", headers=auth_headers)
    assert r.status_code == 422 and "insuffisant" in r.json()["detail"]


def test_best_entered_odds_are_stored(setup):
    c, h, _, mid, _ = setup
    for bk, price in (("A", 2.0), ("B", 2.4)):
        c.post(
            f"/api/v1/matches/{mid}/odds",
            headers=h,
            json={"bookmaker": bk, "market": "1X2", "selection": "home", "price": price},
        )
    _record(c, h, mid)
    rows = {
        (x["market"], x["selection"]): x
        for x in c.get(f"/api/v1/predictions?match_id={mid}").json()
    }
    assert (
        rows[("1X2", "home")]["observed_odds"] == 2.4
        and rows[("1X2", "draw")]["observed_odds"] is None
    )


def test_settlement_on_result_update(setup):
    c, h, cid, mid, _ = setup
    _record(c, h, mid)
    assert c.get("/api/v1/predictions?state=settled").json() == []
    c.patch(
        f"/api/v1/matches/{mid}",
        headers=h,
        json={"status": "finished", "home_score": 3, "away_score": 0},
    )
    out = {
        (x["market"], x["selection"]): x["outcome"]
        for x in c.get(f"/api/v1/predictions?match_id={mid}").json()
    }
    assert (
        out[("1X2", "home")] == "win"
        and out[("1X2", "draw")] == "loss"
        and out[("1X2", "away")] == "loss"
    )
    assert out[("OU", "over")] == "win" and out[("OU", "under")] == "loss"
    assert out[("BTTS", "no")] == "win" and out[("BTTS", "yes")] == "loss"
    assert c.post("/api/v1/predictions/settle", headers=h).json() == {"settled": 0}  # idempotent
    perf = c.get(f"/api/v1/performance?competition_id={cid}").json()
    assert (
        perf["overall"]["settled"] == 3
        and perf["overall"]["reliable"] is False
        and perf["pending_predictions"] == 0
    )
    assert set(perf["by_market"]) == {"1X2", "OU", "BTTS"}


def test_cancelled_match_is_void_and_excluded(setup):
    c, h, _, mid, _ = setup
    _record(c, h, mid)
    c.patch(f"/api/v1/matches/{mid}", headers=h, json={"status": "cancelled"})
    assert {x["outcome"] for x in c.get(f"/api/v1/predictions?match_id={mid}").json()} == {"void"}
    perf = c.get("/api/v1/performance").json()
    assert perf["voided"] == 7 and perf["overall"]["settled"] == 0


def test_database_refuses_modification_even_with_raw_sql(setup):
    c, h, _, mid, db = setup
    _record(c, h, mid)
    c.patch(
        f"/api/v1/matches/{mid}",
        headers=h,
        json={"status": "finished", "home_score": 1, "away_score": 1},
    )
    for sql in (
        "UPDATE predictions SET probability = 0.99",
        "DELETE FROM predictions",
        "UPDATE prediction_results SET outcome = 'win'",
        "DELETE FROM prediction_results",
    ):
        with pytest.raises(DBAPIError):
            db.execute(text(sql))
            db.commit()
        db.rollback()
    assert db.execute(text("SELECT count(*) FROM predictions")).scalar() == 7


def test_unique_slot_enforced_by_database(setup):
    c, h, _, mid, db = setup
    _record(c, h, mid)
    with pytest.raises(DBAPIError):
        db.execute(
            text(
                "INSERT INTO predictions (match_id, model_version_id, market, selection, probability, created_at) "
                "SELECT match_id, model_version_id, market, selection, 0.5, created_at FROM predictions WHERE market='1X2' AND selection='home'"
            )
        )
        db.commit()
    db.rollback()


def test_outcome_logic():
    o = tracking.outcome_of
    assert (
        o("OU", "over", 2.5, 2, 1) == PredictionOutcome.WIN
        and o("OU", "under", 2.5, 1, 1) == PredictionOutcome.WIN
    )
    assert (
        o("BTTS", "yes", None, 1, 1) == PredictionOutcome.WIN
        and o("BTTS", "yes", None, 2, 0) == PredictionOutcome.LOSS
    )
    assert o("1X2", "draw", None, 0, 0) == PredictionOutcome.WIN


def test_summary_metrics_by_hand():
    items = [
        {"probs": {"home": 0.5, "draw": 0.3, "away": 0.2}, "winner": "home", "odds": {"home": 2.2}},
        {"probs": {"home": 0.2, "draw": 0.3, "away": 0.5}, "winner": "draw", "odds": {"away": 3.0}},
    ]
    s = tracking._summarise(items)
    assert s["brier"] == pytest.approx(0.58) and s["log_loss"] == pytest.approx(
        (-math.log(0.5) - math.log(0.3)) / 2
    )
    assert s["hit_rate"] == 0.5 and s["settled"] == 2 and s["reliable"] is False
    assert s["top_pick_bets"] == {
        "n": 2,
        "profit_units": pytest.approx(0.2),
        "roi": pytest.approx(0.1),
    }
    assert s["value_bets"]["n"] == 2 and s["value_bets"]["profit_units"] == pytest.approx(0.2)
    lo, hi = s["hit_rate_ci95"]
    assert 0 <= lo < 0.5 < hi <= 1
    assert tracking._summarise([]) == {"settled": 0, "reliable": False}
