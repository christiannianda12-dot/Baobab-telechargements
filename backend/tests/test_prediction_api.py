from datetime import timedelta

import pytest

from app.models import Competition, Match, Team
from app.models.mixins import DataSource
from app.models.sports import MatchStatus
from tests.synth import league


def _load(db, recs, upto):
    comp = Competition(name="Synthétique", season="test", source=DataSource.DEMO)
    db.add(comp)
    ids = {}
    for t in {x for r in recs for x in (r.home, r.away)}:
        team = Team(name=f"T{t}", source=DataSource.DEMO)
        db.add(team)
        db.flush()
        ids[t] = team.id
    for r in recs[:upto]:
        db.add(
            Match(
                competition_id=comp.id,
                home_team_id=ids[r.home],
                away_team_id=ids[r.away],
                kickoff_at=r.when,
                status=MatchStatus.FINISHED,
                home_score=r.hg,
                away_score=r.ag,
                source=DataSource.DEMO,
            )
        )
    nxt = recs[upto]
    m = Match(
        competition_id=comp.id,
        home_team_id=ids[nxt.home],
        away_team_id=ids[nxt.away],
        kickoff_at=nxt.when + timedelta(hours=1),
        source=DataSource.DEMO,
    )
    db.add(m)
    db.commit()
    return comp.id, m.id


def test_prediction_refused_without_history(client, db_session):
    recs, _ = league()
    _, mid = _load(db_session, recs, upto=10)
    j = client.get(f"/api/v1/matches/{mid}/prediction").json()
    assert j["available"] is False and "insuffisant" in j["reason"] and "probabilities" not in j
    assert j["model"]["name"] == "poisson" and j["limitations"]


def test_prediction_with_history_and_value_on_entered_odds_only(client, db_session, auth_headers):
    recs, _ = league()
    cid, mid = _load(db_session, recs, upto=200)
    j = client.get(f"/api/v1/matches/{mid}/prediction").json()
    assert (
        j["available"] is True and j["value"] == []
    )  # aucune cote saisie => aucune valeur affichée
    p = j["probabilities"]["1X2"]
    assert sum(p.values()) == pytest.approx(1.0) and j["training"]["matches"] == 200
    client.post(
        f"/api/v1/matches/{mid}/odds",
        headers=auth_headers,
        json={"bookmaker": "Manuel", "market": "1X2", "selection": "home", "price": 2.0},
    )
    v = client.get(f"/api/v1/matches/{mid}/prediction").json()["value"]
    assert len(v) == 1 and v[0]["expected_value"] == pytest.approx(p["home"] * 2.0 - 1)


def test_elo_and_backtest_endpoints(client, db_session, auth_headers):
    recs, _ = league()
    cid, _ = _load(db_session, recs, upto=200)
    e = client.get(f"/api/v1/competitions/{cid}/elo").json()
    assert e["matches_used"] == 200 and e["ranking"][0]["rating"] >= e["ranking"][-1]["rating"]
    assert client.get(f"/api/v1/competitions/{cid}/backtest").status_code == 401
    b = client.get(f"/api/v1/competitions/{cid}/backtest", headers=auth_headers).json()
    assert b["brier_skill"] > 0 and b["evaluated"] > 50
    assert client.get("/api/v1/competitions/999/elo").status_code == 404
    assert client.get("/api/v1/matches/999/prediction").status_code == 404
