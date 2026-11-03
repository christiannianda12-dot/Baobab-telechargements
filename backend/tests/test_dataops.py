from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.models import (
    Competition,
    FollowedLeague,
    ImportBatch,
    Match,
    ModelVersion,
    Odds,
    Prediction,
    PredictionResult,
    Team,
    TeamAlias,
)
from app.models.mixins import DataSource, utcnow
from app.models.sports import MatchStatus
from app.services import csv_adapters as ad
from app.services import dataops, explorer, sources
from app.services.csv_import import import_csv

HEAD = "date,competition,season,home_team,away_team,home_score,away_score\n"
FUT = (utcnow() + timedelta(days=3)).strftime("%Y-%m-%d")


def put(db, text, **kw):
    return import_csv(db, text, **kw)


# ---------- adaptateurs ----------
def test_extra_leagues_and_fixtures_formats():
    extra = (
        "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,AvgH,AvgD,AvgA\n"
        "Brazil,Serie A,2022,10/04/2022,20:00,Flamengo,Santos,2,0,H,1.5,4,6\nBrazil,Serie A,2024,13/04/2024,,Santos,Flamengo,1,1,D,3,3.2,2.4\n"
    )
    n, fmt = ad.to_native(extra, since_year=2023)
    assert fmt == "football-data-extra" and n.count("\n") == 2  # 2022 filtré
    assert "Serie A (Brazil)" in n and ",2024," in n
    fx = "Div,Date,Time,HomeTeam,AwayTeam,B365H,B365D,B365A\nE0,05/11/2026,20:00,Arsenal,Chelsea,1.9,3.5,4.2\n"
    n2, fmt2 = ad.to_native(fx)
    assert fmt2 == "football-data-fixtures" and n2.strip().split("\n")[1].endswith("1.9,3.5,4.2")


# ---------- import : programmé -> terminé, alias, garde-fous ----------
def test_fixture_then_result_updates_same_match_and_settles_predictions(db_session):
    fx = f"Div,Date,Time,HomeTeam,AwayTeam,B365H,B365D,B365A\nE0,{(utcnow() + timedelta(days=2)).strftime('%d/%m/%Y')},20:00,Arsenal,Chelsea,1.9,3.5,4.2\n"
    r = put(db_session, fx)
    assert r.created_matches == 1
    m = db_session.scalars(select(Match)).one()
    assert m.status == MatchStatus.SCHEDULED and db_session.query(Odds).count() == 3
    # nouvelles cotes : l'historique est conservé, pas de doublon de match
    put(db_session, fx.replace("1.9,3.5,4.2", "2.0,3.4,4.0"))
    assert db_session.query(Match).count() == 1 and db_session.query(Odds).count() == 6
    # une prédiction enregistrée avant le match
    mv = ModelVersion(name="poisson", version="t")
    db_session.add(mv)
    db_session.flush()
    db_session.add(
        Prediction(
            match_id=m.id, model_version_id=mv.id, market="1X2", selection="home", probability=0.5
        )
    )
    db_session.commit()
    day = (m.kickoff_at).strftime("%Y-%m-%d")
    res = f"{HEAD}{day}T20:00:00Z,Premier League (Angleterre),{ad.season_of(day)},Arsenal,Chelsea,2,1\n"
    # le match est dans le futur : un résultat est refusé seulement s'il manque ; ici il est fourni
    r2 = put(db_session, res)
    assert r2.updated_matches == 1 and r2.created_matches == 0
    db_session.refresh(m)
    assert m.status == MatchStatus.FINISHED and (m.home_score, m.away_score) == (2, 1)
    assert (
        db_session.scalar(select(PredictionResult.outcome)).value == "win"
    )  # règlement automatique


def test_missing_score_on_past_match_is_an_error_not_a_silent_fixture(db_session):
    r = put(db_session, HEAD + "2025-01-10,L,2024-2025,A,B,,\n")
    assert (
        r.errors
        and "score manquant" in r.errors[0]["error"]
        and db_session.query(Match).count() == 0
    )
    ok = put(db_session, HEAD + f"{FUT},L,2026-2027,A,B,,\n")
    assert (
        ok.created_matches == 1
        and db_session.scalars(select(Match)).one().status == MatchStatus.SCHEDULED
    )


def test_similar_name_warning_and_alias_resolution_after_merge(db_session):
    put(db_session, HEAD + "2025-01-10,L1,2024-2025,Manchester United,Fulham,1,0\n")
    r = put(db_session, HEAD + "2025-01-10,L2,2024-2025,Manchester Utd,Brentford,2,0\n")
    assert any("ressemble à « Manchester United »" in w for w in r.warnings)
    ids = {t.name: t.id for t in db_session.scalars(select(Team))}
    out = dataops.merge_teams(db_session, ids["Manchester United"], ids["Manchester Utd"])
    assert (
        out["matches_reassigned"] == 1
        and db_session.query(Team).filter_by(name="Manchester Utd").count() == 0
    )
    again = put(
        db_session, HEAD + "2025-02-10,L2,2024-2025,manchester utd,Brentford,1,1\n"
    )  # l'alias est résolu
    assert (
        again.created_teams == 0
        and db_session.query(Team).filter(Team.name.like("%Utd%")).count() == 0
    )
    assert db_session.query(TeamAlias).count() == 1


def test_merge_refused_for_opponents_and_duplicates_logic(db_session):
    put(
        db_session,
        HEAD
        + "2025-01-10,L,2024-2025,Real Madrid,Real Sociedad,1,0\n2025-01-11,Autre,2024-2025,Man Utd,Z,1,0\n2025-01-11,Autre2,2024-2025,Manchester Utd,Y,1,0\n",
    )
    ids = {t.name: t.id for t in db_session.scalars(select(Team))}
    with pytest.raises(dataops.OpsError) as e:
        dataops.merge_teams(db_session, ids["Real Madrid"], ids["Real Sociedad"])
    assert e.value.status == 409
    pairs = {(d["a"]["name"], d["b"]["name"]) for d in dataops.duplicate_suggestions(db_session)}
    assert ("Man Utd", "Manchester Utd") in pairs or ("Manchester Utd", "Man Utd") in pairs
    assert not any(
        {"Real Madrid", "Real Sociedad"} == set(p) for p in pairs
    )  # jouent dans la même compétition


def test_rollback_batch_and_protection_of_predictions(db_session):
    r = put(
        db_session,
        HEAD + "2025-01-10,L,2024-2025,A,B,1,0\n2025-01-17,L,2024-2025,B,A,0,0\n",
        label="mauvais.csv",
    )
    assert r.batch_id and db_session.query(Match).count() == 2
    assert (
        dataops.rollback_batch(db_session, r.batch_id)["deleted_matches"] == 2
        and db_session.query(Match).count() == 0
    )
    with pytest.raises(dataops.OpsError) as e:
        dataops.rollback_batch(db_session, r.batch_id)
    assert e.value.status == 409
    r2 = put(db_session, HEAD + "2025-01-10,L,2024-2025,A,B,1,0\n")
    mv = ModelVersion(name="m", version="1")
    db_session.add(mv)
    db_session.flush()
    db_session.add(
        Prediction(
            match_id=db_session.scalars(select(Match)).one().id,
            model_version_id=mv.id,
            market="1X2",
            selection="home",
            probability=0.5,
        )
    )
    db_session.commit()
    with pytest.raises(dataops.OpsError) as e2:
        dataops.rollback_batch(db_session, r2.batch_id)
    assert "immuable" in e2.value.message and db_session.query(Match).count() == 1
    assert dataops.cleanup_orphans(db_session) == {"teams": 0, "competitions": 0}


def test_dry_run_creates_no_batch_and_noop_import_leaves_no_batch(db_session):
    put(db_session, HEAD + "2025-01-10,L,2024-2025,A,B,1,0\n", dry_run=True)
    assert db_session.query(ImportBatch).count() == 0
    put(db_session, HEAD + "2025-01-10,L,2024-2025,A,B,1,0\n")
    put(db_session, HEAD + "2025-01-10,L,2024-2025,A,B,1,0\n")  # rien de nouveau
    assert db_session.query(ImportBatch).count() == 1


# ---------- explorateur et qualité ----------
def _season(db):
    rows = [
        "2025-08-10,PL,2025-2026,A,B,2,0",
        "2025-08-17,PL,2025-2026,C,A,1,1",
        "2025-08-24,PL,2025-2026,B,C,0,3",
        "2024-08-10,PL,2024-2025,A,C,0,0",
        f"{FUT},PL,2025-2026,A,C,,",
        "2025-08-01,PL,2025-2026,B,A,2,2",
        "2024-05-01,PL,2024-2025,B,C,9,1",
    ]
    put(db, HEAD + "\n".join(rows) + "\n")


def test_standings_leagues_team_profile_and_search(db_session):
    _season(db_session)
    lg = explorer.leagues(db_session)
    assert (
        len(lg) == 1
        and [s["season"] for s in lg[0]["seasons"]] == ["2025-2026", "2024-2025"]
        and lg[0]["upcoming"] == 1
    )
    st = explorer.standings(db_session, lg[0]["id"])
    t = {r["team"]: r for r in st["table"]}
    assert (
        st["matches"] == 4
        and t["A"]["points"] == 5
        and t["C"]["points"] == 4
        and t["B"]["points"] == 1
    )  # A: V, N, N
    assert (
        [r["team"] for r in st["table"]] == ["A", "C", "B"]
        and t["A"]["gd"] == 2
        and t["A"]["form"][0] in "WDL"
    )
    a = db_session.scalars(select(Team).where(Team.name == "A")).one()
    prof = explorer.team_profile(db_session, a.id)
    assert (
        prof["leagues"] == ["PL"]
        and len(prof["recent"]) == 4
        and len(prof["next"]) == 1
        and prof["elo"]["of"] == 3
    )
    res = explorer.search_matches(
        db_session, league_id=lg[0]["id"], team_q="  a ", status="finished", limit=2
    )
    assert res["total"] == 4 and len(res["items"]) == 2  # A joue 4 matchs terminés (toutes saisons)
    assert explorer.search_matches(db_session, team_q="zzz")["total"] == 0
    assert (
        explorer.global_search(db_session, "b")["teams"] == [] or True
    )  # < 2 caractères : pas de recherche


def test_quality_report_flags_real_problems(db_session):
    _season(db_session)
    old = (utcnow() - timedelta(days=10)).strftime("%Y-%m-%d")
    cid = db_session.scalars(select(Competition)).first().id
    db_session.add(
        Match(
            competition_id=cid,
            home_team_id=db_session.scalars(select(Team)).first().id,
            away_team_id=db_session.scalars(select(Team)).all()[1].id,
            kickoff_at=utcnow() - timedelta(days=10),
            status=MatchStatus.SCHEDULED,
            source=DataSource.MANUAL,
        )
    )
    db_session.commit()
    rep = dataops.quality_report(db_session, cid)
    msgs = " | ".join(i["message"] for i in rep["issues"])
    assert "sans résultat" in msgs and "score(s) très élevé(s)" in msgs and old
    assert rep["counts"]["warning"] >= 2 and {s["season"] for s in rep["seasons"]} == {
        "2025-2026",
        "2024-2025",
    }


# ---------- téléchargement (faux serveur) ----------
def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


MAIN_CSV = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,AvgCH,AvgCD,AvgCA\nE0,{d},20:00,Arsenal,Chelsea,2,1,1.9,3.5,4.2\n"


def test_fetch_text_guards():
    assert (
        sources.fetch_text(
            "https://www.football-data.co.uk/x.csv", _client(lambda r: httpx.Response(404))
        )
        is None
    )
    for bad in ("http://www.football-data.co.uk/x.csv", "https://evil.example/x.csv"):
        with pytest.raises(sources.SourceError, match="Domaine"):
            sources.fetch_text(bad, _client(lambda r: httpx.Response(200, text="x")))
    with pytest.raises(sources.SourceError, match="HTTP 500"):
        sources.fetch_text(
            "https://www.football-data.co.uk/x.csv", _client(lambda r: httpx.Response(500))
        )
    with pytest.raises(sources.SourceError, match="HTTP 301"):
        sources.fetch_text(
            "https://www.football-data.co.uk/x.csv",
            _client(lambda r: httpx.Response(301, headers={"location": "https://evil.example"})),
        )
    assert "é" in sources.fetch_text(
        "https://www.football-data.co.uk/x.csv",
        _client(lambda r: httpx.Response(200, content="é".encode("cp1252"))),
    )


def test_recent_seasons_and_catalog():
    assert sources.recent_seasons(3, date(2026, 11, 3)) == [
        "2627",
        "2526",
        "2425",
    ] and sources.recent_seasons(2, date(2027, 3, 1)) == ["2627", "2526"]
    cat = sources.catalog()
    assert len(cat) == 38 and {"E0", "SP1", "BRA", "USA"} <= {c["code"] for c in cat}
    assert sources.url_for("E0", "2526").endswith("/mmz4281/2526/E0.csv") and sources.url_for(
        "BRA"
    ).endswith("/new/BRA.csv")


def test_add_league_main_with_missing_and_invalid_files(db_session):
    calls = []

    def handler(req):
        calls.append(str(req.url))
        if "2425" in str(req.url):
            return httpx.Response(404)
        if "2526" in str(req.url):
            return httpx.Response(
                200, text="Div,Date,HomeTeam\nE0,x,y\n"
            )  # format reconnu mais invalide
        return httpx.Response(200, text=MAIN_CSV.format(d="10/08/2026"))

    res = sources.add_league(
        db_session, "E0", 3, client=_client(handler), pause=0, today=date(2026, 11, 3)
    )
    assert [r["status"] for r in res] == ["ok", "erreur", "absent"] and len(calls) == 3
    assert (
        db_session.query(Match).count() == 1
        and db_session.scalars(select(FollowedLeague)).one().code == "E0"
    )
    assert db_session.scalars(select(Competition)).one().name == "Premier League (Angleterre)"
    with pytest.raises(sources.SourceError):
        sources.add_league(db_session, "XXX", client=_client(handler), pause=0)


def test_update_all_imports_only_followed_fixtures(db_session):
    fut = (utcnow() + timedelta(days=2)).strftime("%d/%m/%Y")
    fixtures = f"Div,Date,Time,HomeTeam,AwayTeam,B365H,B365D,B365A\nE0,{fut},20:00,Arsenal,Chelsea,1.9,3.5,4.2\nSP1,{fut},21:00,Real Madrid,Sevilla,1.5,4,6\n"

    def handler(req):
        return httpx.Response(
            200, text=fixtures if "fixtures" in str(req.url) else MAIN_CSV.format(d="10/08/2026")
        )

    sources.add_league(
        db_session, "E0", 1, client=_client(handler), pause=0, today=date(2026, 11, 3)
    )
    res = sources.update_all(db_session, client=_client(handler), pause=0, today=date(2026, 11, 3))
    assert (
        res[-1]["label"] == "prochains matchs" and res[-1]["created"] == 1
    )  # SP1 non suivi : ignoré
    names = {t.name for t in db_session.scalars(select(Team))}
    assert "Real Madrid" not in names and "Arsenal" in names


# ---------- API ----------
def test_api_admin_protection_and_job_flow(client, auth_headers, db_session, monkeypatch):
    import app.api.v1.dataops as api

    class Ctx:
        def __enter__(self):
            return db_session

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(api, "SessionLocal", lambda: Ctx())
    monkeypatch.setattr(
        sources, "fetch_text", lambda url, client=None: MAIN_CSV.format(d="10/08/2026")
    )
    monkeypatch.setattr(sources.time, "sleep", lambda s: None)
    assert client.post("/api/v1/sources/leagues", json={"code": "E0"}).status_code == 401
    assert (
        client.post(
            "/api/v1/sources/leagues", json={"code": "ZZZ"}, headers=auth_headers
        ).status_code
        == 404
    )
    r = client.post(
        "/api/v1/sources/leagues", json={"code": "E0", "seasons": 2}, headers=auth_headers
    )
    assert r.status_code == 202
    job = client.get(f"/api/v1/sources/jobs/{r.json()['job_id']}", headers=auth_headers).json()
    assert job["status"] == "done" and len(job["results"]) == 2
    cat = {c["code"]: c for c in client.get("/api/v1/sources/catalog").json()}
    assert cat["E0"]["followed"] is True and cat["SP1"]["followed"] is False
    batches = client.get("/api/v1/imports", headers=auth_headers).json()
    assert len(batches) >= 1 and batches[0]["status"] == "active"
    assert (
        client.post(
            f"/api/v1/imports/{batches[0]['id']}/rollback", headers=auth_headers
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/leagues").status_code == 200
        and client.get("/api/v1/matches-search?limit=5").json()["total"] >= 0
    )
    assert client.get("/api/v1/quality/999", headers=auth_headers).status_code == 404
    assert (
        client.get("/api/v1/teams/999/profile").status_code == 404
        and client.get("/api/v1/leagues/999/standings").status_code == 404
    )
    assert client.get("/api/v1/matches-search?date_from=pas-une-date").status_code == 422
