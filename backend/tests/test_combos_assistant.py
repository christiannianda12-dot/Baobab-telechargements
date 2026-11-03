from datetime import timedelta

import pytest
from sqlalchemy import select

from app.assistant import engine
from app.ml import poisson
from app.models import Match, Team
from app.models.mixins import DataSource, utcnow
from app.services import combos
from tests.synth import league
from tests.test_prediction_api import _load


@pytest.fixture
def world(client, db_session, auth_headers):
    recs, _ = league()
    cid, mid = _load(db_session, recs, upto=200)
    ids = {t.name: t.id for t in db_session.scalars(select(Team))}
    upcoming = []
    for k, (a, b) in enumerate([(1, 2), (3, 4), (5, 6), (7, 8)], start=1):
        m = Match(
            competition_id=cid,
            home_team_id=ids[f"T{a}"],
            away_team_id=ids[f"T{b}"],
            kickoff_at=utcnow() + timedelta(days=k),
            source=DataSource.DEMO,
        )
        db_session.add(m)
        db_session.flush()
        upcoming.append(m.id)
    db_session.commit()
    return {
        "c": client,
        "h": auth_headers,
        "db": db_session,
        "cid": cid,
        "past": mid,
        "up": upcoming,
        "ids": ids,
    }


def leg(mid, market, sel, line=None):
    return {"match_id": mid, "market": market, "selection": sel, "line": line}


def test_predicates_agree_with_market_probabilities():
    lh, la = 1.6, 1.1
    mk, mat = poisson.markets(lh, la), poisson.score_matrix(lh, la)
    for market, sel, line in combos.CANDIDATES + [("1X2", "draw", None)]:
        expect = mk["OU"][str(line)][sel] if market == "OU" else mk[market][sel]
        assert combos._prob(mat, [combos.predicate(market, sel, line)]) == pytest.approx(expect)


def test_independent_matches_multiply_but_same_match_does_not(world):
    db, up = world["db"], world["up"]
    r = combos.analyze(db, [leg(up[0], "1X2", "home"), leg(up[1], "BTTS", "yes")])
    assert r["valid"] and r["joint_probability"] == pytest.approx(
        r["legs"][0]["probability"] * r["legs"][1]["probability"]
    )
    assert r["same_match_groups"] == []
    r2 = combos.analyze(db, [leg(up[0], "1X2", "home"), leg(up[0], "OU", "over", 2.5)])
    g = r2["same_match_groups"][0]
    assert g["joint_probability"] != pytest.approx(
        g["naive_product"], rel=1e-3
    )  # corrélées : pas de produit naïf
    assert r2["joint_probability"] == pytest.approx(g["joint_probability"])
    assert any("corrélées" in w for w in r2["warnings"])


def test_incompatible_and_unavailable_and_duplicates(world):
    db, up = world["db"], world["up"]
    r = combos.analyze(db, [leg(up[0], "1X2", "home"), leg(up[0], "1X2", "away")])
    assert r["valid"] is False and "incompatibles" in r["problems"][0]
    assert (
        combos.analyze(db, [leg(up[0], "1X2", "home"), leg(up[0], "1X2", "home")])["valid"] is False
    )
    assert combos.analyze(db, [leg(9999, "1X2", "home")])["valid"] is False


def test_odds_total_and_expected_value(world):
    c, h, up = world["c"], world["h"], world["up"]
    r0 = c.post(
        "/api/v1/combos/analyze",
        headers=h,
        json={"legs": [leg(up[0], "1X2", "home"), leg(up[1], "1X2", "home")]},
    ).json()
    assert r0["total_odds"] is None and any("Cote totale non calculée" in w for w in r0["warnings"])
    for mid, price in ((up[0], 2.0), (up[1], 1.8)):
        c.post(
            f"/api/v1/matches/{mid}/odds",
            headers=h,
            json={"bookmaker": "M", "market": "1X2", "selection": "home", "price": price},
        )
    r = c.post(
        "/api/v1/combos/analyze",
        headers=h,
        json={"legs": [leg(up[0], "1X2", "home"), leg(up[1], "1X2", "home")]},
    ).json()
    assert r["total_odds"] == pytest.approx(3.6)
    assert r["expected_value"] == pytest.approx(r["joint_probability"] * 3.6 - 1)


def test_combo_api_validation_and_suggest(world):
    c, h, up = world["c"], world["h"], world["up"]
    assert c.post("/api/v1/combos/analyze", json={"legs": []}).status_code == 401
    bad = c.post(
        "/api/v1/combos/analyze", headers=h, json={"legs": [leg(up[0], "OU", "over", 9.5)]}
    )
    assert bad.status_code == 422
    s = c.post("/api/v1/combos/suggest", headers=h, json={"size": 3}).json()
    assert s["valid"] and len(s["legs"]) == 3 and len({x["match_id"] for x in s["legs"]}) == 3
    assert s["joint_probability"] == pytest.approx(s["naive_product"])  # un seul marché par match
    probs = sorted((x["probability"] for x in s["legs"]), reverse=True)
    assert probs[0] >= probs[-1]
    few = c.post("/api/v1/combos/suggest", headers=h, json={"size": 3, "match_ids": [up[0]]}).json()
    assert few["valid"] is False


def test_team_extraction_is_word_bounded_and_accent_insensitive(world):
    db = world["db"]
    db.add(Team(name="Étoile Sportive", source=DataSource.MANUAL))
    db.commit()
    assert [t.name for t in engine.find_teams(db, "analyse T10 contre T2")] == [
        "T10",
        "T2",
    ]  # T1 n'est pas dans T10
    assert [t.name for t in engine.find_teams(db, "que vaut etoile sportive ?")] == [
        "Étoile Sportive"
    ]


def test_assistant_requires_auth_and_reports_no_llm(world):
    c, h = world["c"], world["h"]
    assert c.post("/api/v1/assistant/chat", json={"message": "bonjour"}).status_code == 401
    st = c.get("/api/v1/assistant/status").json()
    assert st["llm_enabled"] is False and st["engine"] == "rules"
    r = c.post("/api/v1/assistant/chat", headers=h, json={"message": "bonjour"}).json()
    assert r["intent"] == "help" and r["engine"] == "rules" and r["llm_enabled"] is False


def test_assistant_analysis_matches_the_model_exactly(world):
    c, h, past = world["c"], world["h"], world["past"]
    m = world["db"].get(Match, past)
    home, away = (
        world["db"].get(Team, m.home_team_id).name,
        world["db"].get(Team, m.away_team_id).name,
    )
    r = c.post(
        "/api/v1/assistant/chat", headers=h, json={"message": f"Analyse {home} contre {away}."}
    ).json()
    assert r["intent"] == "analyze" and r["data"]["match_id"] == past
    p = c.get(f"/api/v1/matches/{past}/prediction").json()["probabilities"]["1X2"]
    assert engine.pct(p["home"]) in r["answer"] and engine.pct(p["draw"]) in r["answer"]
    assert "Limites" in r["answer"] and "Modèle poisson" in r["answer"]


def test_assistant_never_invents_when_data_is_missing(world):
    c, h = world["c"], world["h"]
    unknown = c.post(
        "/api/v1/assistant/chat", headers=h, json={"message": "Analyse Arsenal contre Chelsea"}
    ).json()
    assert "pas identifié" in unknown["answer"] and unknown["data"] == {}
    db = world["db"]
    db.add_all(
        [Team(name="Zeta", source=DataSource.MANUAL), Team(name="Omega", source=DataSource.MANUAL)]
    )
    db.commit()
    nomatch = c.post(
        "/api/v1/assistant/chat", headers=h, json={"message": "Analyse Zeta contre Omega"}
    ).json()
    assert "Aucun match enregistré" in nomatch["answer"] and "%" not in nomatch["answer"]
    m = Match(
        competition_id=world["cid"],
        home_team_id=db.scalar(select(Team.id).where(Team.name == "Zeta")),
        away_team_id=db.scalar(select(Team.id).where(Team.name == "Omega")),
        kickoff_at=utcnow() + timedelta(days=2),
    )
    db.add(m)
    db.commit()
    thin = c.post(
        "/api/v1/assistant/chat", headers=h, json={"message": "Analyse Zeta contre Omega"}
    ).json()
    assert "Je ne produis pas de probabilité" in thin["answer"] and "1X2 :" not in thin["answer"]


def test_assistant_compare_best_markets_and_combo(world):
    c, h = world["c"], world["h"]
    cmp_ = c.post("/api/v1/assistant/chat", headers=h, json={"message": "Compare T1 et T2"}).json()
    assert cmp_["intent"] == "compare" and "T1" in cmp_["answer"] and "T2" in cmp_["answer"]
    best = c.post(
        "/api/v1/assistant/chat",
        headers=h,
        json={"message": "Quels sont les marchés les plus intéressants statistiquement ?"},
    ).json()
    assert (
        best["intent"] == "best_markets"
        and "probables" in best["answer"]
        and "pas une valeur" in best["answer"]
    )
    combo = c.post(
        "/api/v1/assistant/chat",
        headers=h,
        json={
            "message": "Construis un combiné de trois rencontres en privilégiant les probabilités élevées"
        },
    ).json()
    assert (
        combo["intent"] == "combo"
        and len(combo["data"]["legs"]) == 3
        and "Probabilité conjointe" in combo["answer"]
    )
    two = c.post(
        "/api/v1/assistant/chat", headers=h, json={"message": "un combiné de 2 matchs"}
    ).json()
    assert len(two["data"]["legs"]) == 2


def test_assistant_combo_without_upcoming_matches(client, auth_headers):
    r = client.post(
        "/api/v1/assistant/chat", headers=auth_headers, json={"message": "combiné de 3 matchs"}
    ).json()
    assert "Aucun match à venir" in r["answer"]
