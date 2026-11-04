"""Automatisation : cycle planifié, enregistrement automatique, The Odds API, combinés proposés, aperçu du jour."""

import json
from datetime import timedelta
from math import prod

import httpx
import pytest
from sqlalchemy import select

from app.models import AutomationRun, FollowedLeague, Odds, Prediction
from app.models.mixins import DataSource, utcnow
from app.services import appsettings, automation, oddsapi, proposals, sources
from app.services.csv_import import import_csv
from tests.test_combos_assistant import world  # noqa: F401  (ligue synthétique + 4 matchs à venir)


class Ctx:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *a):
        return False


def _odds(db, mid, home, draw, away, over=None, under=None, book="Bet365"):
    for sel, p in (("home", home), ("draw", draw), ("away", away)):
        db.add(
            Odds(
                match_id=mid,
                bookmaker=book,
                market="1X2",
                selection=sel,
                price=p,
                recorded_at=utcnow(),
                source=DataSource.MANUAL,
            )
        )
    for sel, p in (("over", over), ("under", under)):
        if p:
            db.add(
                Odds(
                    match_id=mid,
                    bookmaker=book,
                    market="OU",
                    selection=sel,
                    line=2.5,
                    price=p,
                    recorded_at=utcnow(),
                    source=DataSource.MANUAL,
                )
            )


# ---------- enregistrement automatique + cycle ----------
def test_record_upcoming_records_once_and_never_invents(world):  # noqa: F811
    db, up = world["db"], world["up"]
    r = automation.record_upcoming(db, hours=60)  # matchs à +1 et +2 jours
    assert r == {"recorded": 2, "no_model": 0, "already": 0}
    assert db.query(Prediction).count() == 14  # 7 issues par match
    assert automation.record_upcoming(db, hours=60) == {"recorded": 0, "no_model": 0, "already": 2}
    assert (
        db.query(Prediction).filter(Prediction.match_id == up[3]).count() == 0
    )  # hors fenêtre : rien


def test_cycle_runs_every_step_even_if_one_fails_and_is_logged(world, monkeypatch):  # noqa: F811
    db = world["db"]
    db.add(FollowedLeague(code="E0"))
    db.commit()
    monkeypatch.setattr(
        sources,
        "update_all",
        lambda *a, **k: [
            {"label": "E0 2627", "status": "ok", "created": 3, "updated": 1, "ignored": 2}
        ],
    )
    res = automation.run_cycle(lambda: Ctx(db), "manual")
    assert res["status"] == "ok" and res["summary"]["update"] == {
        "files": 1,
        "created": 3,
        "updated": 1,
        "ignored": 2,
        "errors": [],
    }
    assert res["summary"]["predictions"]["recorded"] >= 1 and "settled" in res["summary"]
    run = db.scalars(select(AutomationRun)).one()
    assert (
        run.trigger == "manual"
        and run.finished_at
        and json.loads(run.summary)["update"]["created"] == 3
    )

    def boom(*a, **k):
        raise RuntimeError("site inaccessible")

    monkeypatch.setattr(sources, "update_all", boom)
    res2 = automation.run_cycle(lambda: Ctx(db), "auto")
    assert (
        res2["status"] == "partial"
        and "site inaccessible" in res2["summary"]["update"]["error"]
        and "settled" in res2["summary"]
    )  # les autres étapes ont tourné


def test_cycle_refuses_to_overlap(world):  # noqa: F811
    assert automation.RUN_LOCK.acquire(blocking=False)
    try:
        assert automation.run_cycle(lambda: Ctx(world["db"]), "auto") is None
    finally:
        automation.RUN_LOCK.release()


def test_schedule_due_logic(db_session):
    assert automation.is_due(db_session)  # jamais exécuté : dû immédiatement
    db_session.add(AutomationRun(trigger="auto", status="ok", finished_at=utcnow()))
    db_session.commit()
    assert not automation.is_due(db_session) and automation.next_run_at(
        db_session
    ) > utcnow() + timedelta(hours=5)
    appsettings.put(db_session, "auto_interval_hours", "1")
    db_session.query(AutomationRun).update({"finished_at": utcnow() - timedelta(hours=2)})
    db_session.commit()
    assert automation.is_due(db_session)
    appsettings.put(db_session, "auto_enabled", "0")
    assert automation.next_run_at(db_session) is None and not automation.is_due(db_session)


# ---------- The Odds API ----------
def _api_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _event(home="Arsenal", away="Chelsea", when=None):
    return [
        {
            "id": "x",
            "commence_time": (when or utcnow() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "home_team": home,
            "away_team": away,
            "bookmakers": [
                {
                    "key": "onexbet",
                    "title": "1xBet",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": home, "price": 2.05},
                                {"name": away, "price": 3.6},
                                {"name": "Draw", "price": 3.4},
                            ],
                        },
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "point": 2.5, "price": 1.9},
                                {"name": "Under", "point": 2.5, "price": 1.95},
                                {"name": "Over", "point": 4.5, "price": 5.0},
                            ],
                        },
                    ],
                }
            ],
        }
    ]


def test_odds_api_adds_named_bookmaker_odds_and_respects_quota(db_session):
    d = (utcnow() + timedelta(days=2)).strftime("%d/%m/%Y")
    import_csv(
        db_session,
        f"Div,Date,Time,HomeTeam,AwayTeam,B365H,B365D,B365A\nE0,{d},20:00,Arsenal,Chelsea,1.9,3.5,4.2\n",
    )
    db_session.add(FollowedLeague(code="E0"))
    appsettings.put(db_session, "odds_api_key", "secret-key")
    seen = []

    def handler(req):
        seen.append(req.url.path)
        if req.url.path.endswith("/sports"):
            return httpx.Response(200, json=[{"key": "soccer_epl"}, {"key": "soccer_other"}])
        return httpx.Response(200, json=_event(), headers={"x-requests-remaining": "400"})

    s = oddsapi.refresh_odds(db_session, _api_client(handler), pause=0)
    assert (
        s["matched"] == 1 and s["odds_added"] == 3 + 2 and s["requests"] == 1 and not s["errors"]
    )  # la ligne 4,5 buts est ignorée
    rows = db_session.query(Odds).filter(Odds.bookmaker == "1xBet").all()
    assert (
        len(rows) == 5
        and {o.source for o in rows} == {DataSource.API}
        and appsettings.get(db_session, "odds_api_remaining") == "400"
    )
    assert (
        oddsapi.refresh_odds(db_session, _api_client(handler), pause=0)["odds_added"] == 0
    )  # rien de changé

    # quota presque épuisé : on s'arrête et on le dit
    def low(req):
        return (
            httpx.Response(200, json=[{"key": "soccer_epl"}])
            if req.url.path.endswith("/sports")
            else httpx.Response(200, json=_event(), headers={"x-requests-remaining": "10"})
        )

    assert (
        "quota presque épuisé"
        in oddsapi.refresh_odds(db_session, _api_client(low), pause=0)["stopped"]
    )


def test_odds_api_without_key_and_key_errors(db_session):
    assert oddsapi.refresh_odds(db_session)["skipped"] == "pas de clé The Odds API"
    with pytest.raises(oddsapi.OddsApiError, match="401"):
        oddsapi.test_key("bad", _api_client(lambda r: httpx.Response(401)))
    ok = oddsapi.test_key(
        "k",
        _api_client(
            lambda r: httpx.Response(
                200,
                json=[{"key": "soccer_epl"}, {"key": "tennis"}],
                headers={"x-requests-remaining": "480"},
            )
        ),
    )
    assert ok == {"ok": True, "soccer_competitions": 1, "remaining": "480", "used": None}


def test_secret_key_is_never_exposed(db_session):
    appsettings.put(db_session, "odds_api_key", "super-secret")
    pub = appsettings.public(db_session)
    assert pub["odds_api_key_set"] is True and "super-secret" not in json.dumps(pub)


# ---------- combinés proposés ----------
def _market(db, up):
    for mid in up:  # marché cohérent : favori léger à domicile, plus/moins 2,5 équilibré
        _odds(db, mid, 2.0, 3.6, 4.0, 1.9, 1.95, book="Moyenne du marché")
        _odds(db, mid, 2.1, 3.7, 4.2, 1.95, 2.0, book="Bet365")
        _odds(db, mid, 2.05, 3.65, 4.1, 1.92, 1.97, book="Pinnacle")
    db.commit()


def test_best_odds_blend_and_ranking_are_consistent(world):  # noqa: F811
    db, up = world["db"], world["up"]
    _market(db, up)
    res = proposals.build(db, "equilibre", days=10)
    assert res["weights"] == {"marche": 0.7, "modele": 0.3} and res["proposals"], res
    ev = [p["expected_value"] for p in res["proposals"]]
    assert ev == sorted(ev, reverse=True)  # classé par valeur espérée décroissante
    for p in res["proposals"]:
        legs = p["legs"]
        assert len({leg["match_id"] for leg in legs}) == len(legs) and 3 <= len(legs) <= 4
        assert (
            p["total_odds"] == pytest.approx(prod(leg["odds"] for leg in legs))
            and 4.0 <= p["total_odds"] <= 14.0
        )
        assert p["joint_probability"] == pytest.approx(prod(leg["p_final"] for leg in legs))
        assert p["expected_value"] == pytest.approx(
            p["joint_probability"] * p["total_odds"] - 1
        ) and p["risk"] in {"faible", "modéré", "élevé"}
        for leg in legs:
            assert (
                leg["bookmaker"] == "Bet365"
                and leg["basis"] == "modèle + marché"
                and leg["p_final"] == pytest.approx(0.7 * leg["p_market"] + 0.3 * leg["p_model"])
            )
            assert leg["odds"] >= leg["avg_odds"] and leg["edge"] == pytest.approx(
                leg["p_final"] * leg["odds"] - 1
            )
    assert any("négative" in n for n in res["proposals"][0]["notes"]) or any(
        "positive" in n for n in res["proposals"][0]["notes"]
    )


def test_profiles_and_empty_reasons(world):  # noqa: F811
    db, up = world["db"], world["up"]
    assert proposals.build(db, "prudent")["empty_reason"].startswith(
        "Aucun match à venir avec des cotes"
    )  # pas de cotes du tout
    _market(db, up)
    assert (
        proposals.build(db, "prudent", days=10)["empty_reason"]
        == "Aucune combinaison ne respecte les critères de ce profil sur cet horizon."
    )  # pas de gros favoris
    amb = proposals.build(db, "ambitieux", days=10)
    assert amb["proposals"] and all(
        12 <= p["total_odds"] <= 80 and 4 <= len(p["legs"]) <= 5 for p in amb["proposals"]
    )


def test_market_only_fallback_when_model_unavailable(client, db_session, auth_headers):
    d = (utcnow() + timedelta(days=1)).strftime("%d/%m/%Y")
    import_csv(
        db_session,
        f"Div,Date,Time,HomeTeam,AwayTeam,AvgH,AvgD,AvgA,B365H,B365D,B365A\nE0,{d},20:00,Nouvelle A,Nouvelle B,2.0,3.6,4.0,2.1,3.7,4.2\n",
    )
    c = proposals.candidates(db_session, 5)
    assert c and all(
        x["basis"] == "marché seul (modèle indisponible)" and x["p_model"] is None for x in c
    )  # jamais de probabilité inventée


# ---------- API ----------
def test_today_overview_and_recorded_flag(world):  # noqa: F811
    c, db, up = world["c"], world["db"], world["up"]
    _market(db, up)
    rows = c.get("/api/v1/today?days=10").json()
    assert (
        len(rows) == 4
        and rows[0]["probabilities"]
        and sum(rows[0]["probabilities"].values()) == pytest.approx(1.0)
    )
    assert (
        rows[0]["best_odds"]["home"] == {"price": 2.1, "bookmaker": "Bet365"}
        and rows[0]["recorded"] is False
    )
    automation.record_upcoming(db, 60)
    assert [r["recorded"] for r in c.get("/api/v1/today?days=10").json()] == [
        True,
        True,
        False,
        False,
    ]


def test_automation_api_permissions_and_flow(world, monkeypatch, client, db_session):  # noqa: F811
    c, h = world["c"], world["h"]
    assert c.get("/api/v1/automation/status").status_code == 401
    st = c.get("/api/v1/automation/status", headers=h).json()
    assert (
        st["settings"]["auto_enabled"] is True
        and st["settings"]["odds_api_key_set"] is False
        and st["running"] is False
    )
    upd = c.put(
        "/api/v1/automation/settings",
        headers=h,
        json={"auto_interval_hours": 3, "odds_api_key": "abc123", "auto_record": False},
    )
    assert (
        upd.status_code == 200
        and upd.json()["auto_interval_hours"] == 3
        and upd.json()["odds_api_key_set"] is True
        and "abc123" not in upd.text
    )
    assert (
        c.put("/api/v1/automation/settings", headers=h, json={"auto_interval_hours": 5}).status_code
        == 422
    )  # valeur hors liste
    called = []
    monkeypatch.setattr(
        automation, "run_cycle", lambda factory, trigger, client=None: called.append(trigger)
    )
    assert c.post("/api/v1/automation/run", headers=h).status_code == 202 and called == ["manual"]
    monkeypatch.setattr(
        oddsapi,
        "test_key",
        lambda key, client=None: {
            "ok": True,
            "soccer_competitions": 12,
            "remaining": "490",
            "used": "10",
        },
    )
    assert c.post("/api/v1/automation/odds-key/test", headers=h).json()["remaining"] == "490"
    c.put("/api/v1/automation/settings", headers=h, json={"odds_api_key": ""})
    assert c.post("/api/v1/automation/odds-key/test", headers=h).status_code == 422  # clé effacée
    assert c.get("/api/v1/combos/proposals?profile=equilibre", headers=h).status_code == 200
    assert c.get("/api/v1/combos/proposals?profile=nimporte", headers=h).status_code == 422
