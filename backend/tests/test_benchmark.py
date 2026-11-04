import io

import pytest

from app.models import Odds
from app.services import benchmark
from app.services.csv_import import CLOSING_BOOKMAKER
from tests.synth import league

HEAD = "date,competition,season,home_team,away_team,home_score,away_score,close_home,close_draw,close_away\n"


def _post(client, h, text):
    return client.post(
        "/api/v1/import/matches",
        headers=h,
        files={"file": ("a.csv", io.BytesIO(text.encode()), "text/csv")},
    ).json()


def test_closing_odds_imported_enriched_and_validated(client, auth_headers, db_session):
    row = "2026-01-10,L,2025-2026,A,B,2,1,2.0,3.5,4.0\n"
    r = _post(client, auth_headers, HEAD + row)
    assert (
        r["created_matches"] == 1
        and db_session.query(Odds).filter_by(bookmaker=CLOSING_BOOKMAKER).count() == 3
    )
    # un match déjà importé SANS cotes les reçoit au second import (enrichissement), une seule fois
    _post(
        client,
        auth_headers,
        "date,competition,season,home_team,away_team,home_score,away_score\n2026-02-10,L,2025-2026,A,B,0,0\n",
    )
    r2 = _post(client, auth_headers, HEAD + "2026-02-10,L,2025-2026,A,B,0,0,2.2,3.3,3.5\n")
    assert r2["skipped_duplicates"] == 1 and r2["enriched_odds"] == 1
    assert (
        _post(client, auth_headers, HEAD + "2026-02-10,L,2025-2026,A,B,0,0,2.2,3.3,3.5\n")[
            "enriched_odds"
        ]
        == 0
    )
    bad = client.post(
        "/api/v1/import/matches",
        headers=auth_headers,
        files={
            "file": (
                "a.csv",
                io.BytesIO((HEAD + "2026-03-01,L,2025-2026,A,B,1,0,0.9,3.3,3.5\n").encode()),
                "text/csv",
            )
        },
    )
    assert bad.status_code == 422
    partial = client.post(
        "/api/v1/import/matches",
        headers=auth_headers,
        files={
            "file": (
                "a.csv",
                io.BytesIO((HEAD + "2026-03-01,L,2025-2026,A,B,1,0,2.0,,3.5\n").encode()),
                "text/csv",
            )
        },
    )
    assert partial.status_code == 422 and "ensemble ou aucune" in str(partial.json())


def _load_with_market(db, market_quality):
    """Ligue synthétique + cotes de clôture dérivées des vraies probabilités (market_quality=1) ou de bruit (0)."""
    from app.models import Competition, Match, Team
    from app.models.mixins import DataSource
    from app.models.sports import MatchStatus

    recs, strength = league()
    comp = Competition(name="Synth", season="s", source=DataSource.DEMO)
    db.add(comp)
    ids = {}
    for t in {x for r in recs for x in (r.home, r.away)}:
        team = Team(name=f"T{t}", source=DataSource.DEMO)
        db.add(team)
        db.flush()
        ids[t] = team.id
    for r in recs:
        m = Match(
            competition_id=comp.id,
            home_team_id=ids[r.home],
            away_team_id=ids[r.away],
            kickoff_at=r.when,
            status=MatchStatus.FINISHED,
            home_score=r.hg,
            away_score=r.ag,
            source=DataSource.DEMO,
        )
        db.add(m)
        db.flush()
        if (
            market_quality
        ):  # marché « parfaitement informé » : il connaît la vraie force des équipes
            sh, sa = strength[r.home], strength[r.away]
            w = [1.25 * sh / (sh + sa), 0.30, sa / (sh + sa)]
            tot = sum(w)
            for sel, p in zip(("home", "draw", "away"), w, strict=True):
                db.add(
                    Odds(
                        match_id=m.id,
                        bookmaker=CLOSING_BOOKMAKER,
                        market="1X2",
                        selection=sel,
                        price=0.95 * tot / p,
                        recorded_at=r.when,
                        source=DataSource.DEMO,
                    )
                )
    db.commit()
    return comp.id


def test_benchmark_unavailable_without_closing_odds(db_session):
    cid = _load_with_market(db_session, 0)
    r = benchmark.compute(db_session, cid)
    assert r["available"] is False and "cotes de clôture" in r["reason"]


def test_benchmark_compares_on_identical_matches_and_reports_value_bets(client, db_session):
    cid = _load_with_market(db_session, 1)
    r = client.get(f"/api/v1/benchmark/{cid}").json()
    assert r["available"] and r["matches"] == r["evaluated_by_model"] > 100
    s = r["scores"]
    assert (
        s["chance"]["brier"] == pytest.approx(2 / 3)
        and s["baseline"]["brier"] > s["model"]["brier"] > 0
    )
    d = r["model_minus_market"]["brier"]
    assert d["mean"] == pytest.approx(s["model"]["brier"] - s["market"]["brier"]) and d["se"] > 0
    assert sum(x["matches"] for x in r["by_season"]) == r["matches"]
    thr = [v["min_expected_value"] for v in r["value_bets"]]
    assert (
        thr == sorted(thr) and r["value_bets"][0]["bets"] >= r["value_bets"][-1]["bets"]
    )  # seuil plus strict => moins de paris
    assert "verdict" in r and r["notes"]
    assert r["calibration"]["model"] and r["cumulative"][-1]["brier_gap"] == pytest.approx(
        d["mean"] * r["matches"]
    )
    assert client.get("/api/v1/benchmark/999").status_code == 404
