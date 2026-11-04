"""Version 3 : coupes UEFA (Football.TXT), mode tolérant, reconnaissance d'équipes, nouvelles tentatives."""

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.models import Match, Team
from app.models.sports import MatchStatus
from app.services import csv_adapters as ad
from app.services import sources
from app.services.csv_import import import_csv
from app.services.names import norm_key, resolve_existing

EXCERPT = (Path(__file__).parent / "data" / "uefa_excerpt.txt").read_text(
    encoding="utf-8"
)  # extrait réel openfootball (domaine public)
HEAD = "date,competition,season,home_team,away_team,home_score,away_score\n"


# ---------- Football.TXT ----------
def test_footballtxt_parsing_scores_years_and_stages():
    native, fmt = ad.to_native(EXCERPT)
    rows = [r.split(",") for r in native.strip().split("\n")[1:]]
    assert fmt == "football-txt" and len(rows) == 17 or len(rows) >= 14
    by = {(r[3], r[4]): r for r in rows}
    assert by[("Athletic Club", "Arsenal FC")][:3] == [
        "2025-09-16T18:45:00Z",
        "UEFA Champions League",
        "2025-2026",
    ]
    assert by[("Athletic Club", "Arsenal FC")][5:] == ["0", "2", "0", "0"]
    assert by[("Juventus FC", "Borussia Dortmund")][0].startswith(
        "2025-09-16T21:00"
    )  # l'heure s'applique aux lignes suivantes
    assert by[("PSV", "Royale Union Saint-Gilloise")][0].startswith(
        "2025-09-16T18:45"
    )  # sans heure : celle de la ligne précédente
    assert by[("FK Kairat", "PAE Olympiakos SFP")][0].startswith("2025-12-09")
    assert by[("FK Kairat", "Club Brugge KV")][0].startswith("2026-01-20")
    # tirs au but + prolongations : score des 90 minutes (1-1), mi-temps 0-1
    assert by[("Paris Saint-Germain FC", "Arsenal FC")][5:] == ["1", "1", "0", "1"] and by[
        ("Paris Saint-Germain FC", "Arsenal FC")
    ][0].startswith("2026-05-30")
    # prolongations seules : score après 90 minutes (3-0)
    assert by[("Juventus FC", "Galatasaray SK")][5:7] == ["3", "0"] and by[
        ("Juventus FC", "Galatasaray SK")
    ][0].startswith("2026-02-25")
    # match à venir sans score : programmé
    assert by[("Club Futur", "Équipe Test")][5:7] == ["", ""] and by[("Club Futur", "Équipe Test")][
        0
    ].startswith("2099-12-01")


def test_cup_import_creates_competition_scheduled_and_finished_matches(db_session):
    r = import_csv(db_session, EXCERPT, tolerant=True)
    assert not r.errors and r.source_format == "football-txt" and r.created_matches >= 14
    comps = {
        (c.name, c.season)
        for c in db_session.query(__import__("app.models", fromlist=["Competition"]).Competition)
    }
    assert comps == {("UEFA Champions League", "2025-2026")}
    sched = db_session.scalars(select(Match).where(Match.status == MatchStatus.SCHEDULED)).all()
    assert len(sched) == 1 and sched[0].kickoff_at.year == 2099
    assert import_csv(db_session, EXCERPT, tolerant=True).created_matches == 0  # idempotent


# ---------- mode tolérant ----------
def test_tolerant_mode_ignores_a_few_bad_rows_but_refuses_bad_files(db_session):
    good = "".join(f"2025-01-{d:02d},L,2024-2025,A{d},B{d},1,0\n" for d in range(1, 29))
    text = (
        HEAD + good + "2025-01-30,L,2024-2025,P,Q,,\n" + "pas-une-date,L,2024-2025,R,S,1,1\n"
    )  # reporté + date illisible
    strict = import_csv(db_session, text)
    assert strict.errors and db_session.query(Match).count() == 0  # import manuel : tout-ou-rien
    t = import_csv(db_session, text, tolerant=True)
    assert (
        not t.errors
        and t.created_matches == 28
        and t.ignored_count == 2
        and "score manquant" in t.ignored[0]["error"]
    )
    many = HEAD + "x,L,s,A,B,1,0\n" * 10 + "2025-01-01,L,2024-2025,C,D,1,0\n"
    assert import_csv(
        db_session, many, tolerant=True
    ).errors  # > 5 % d'erreurs : fichier mauvais, refusé
    assert import_csv(
        db_session, "date,competition\n1,2\n", tolerant=True
    ).errors  # en-tête invalide : toujours refusé


# ---------- reconnaissance d'équipes ----------
def test_resolve_existing_rules_are_cautious():
    class T:
        def __init__(self, n):
            self.name = n

    known = {
        norm_key(n): T(n)
        for n in [
            "Arsenal",
            "Man United",
            "Man City",
            "Ath Madrid",
            "Real Madrid",
            "Sociedad",
            "Milan",
            "Inter",
            "Bologna",
            "West Ham",
            "Brighton",
            "Leicester",
        ]
    }
    r = lambda n: (lambda x: x and (x[0].name, x[1]))(resolve_existing(norm_key(n), known))  # noqa: E731
    assert (
        r("Bologna FC") == ("Bologna", "même nom hors préfixe/suffixe")
        and r("Arsenal FC")[0] == "Arsenal"
    )
    assert (
        r("Manchester United FC")[0] == "Man United" and r("Manchester City")[0] == "Man City"
    )  # table d'alias
    assert r("Club Atlético de Madrid")[0] == "Ath Madrid" and r("AC Milan")[0] == "Milan"
    assert r("Real Madrid CF")[0] == "Real Madrid" and r("Real Sociedad de Fútbol")[0] == "Sociedad"
    assert (
        r("West Ham United")[0] == "West Ham"
        and r("Brighton & Hove Albion")[0] == "Brighton"
        and r("Leicester City")[0] == "Leicester"
        and r("Real Betis") is None
        and r("Inter Miami") is None
        and r("Manchester Metropolitan") is None
    )  # jamais de fusion hasardeuse


def test_cup_teams_reuse_league_teams_without_duplicates(db_session):
    import_csv(
        db_session, HEAD + "2025-09-01,Premier League (Angleterre),2025-2026,Arsenal,Man City,2,1\n"
    )
    r = import_csv(db_session, EXCERPT, tolerant=True)
    names = [t.name for t in db_session.scalars(select(Team))]
    assert (
        "Arsenal FC" not in names
        and names.count("Arsenal") == 1
        and "Manchester City FC" not in names
    )
    assert r.auto_matched >= 2 and any("↔" in w for w in r.warnings)


# ---------- catalogue et téléchargement des coupes ----------
def test_cups_in_catalog_and_urls():
    cat = {c["code"]: c for c in sources.catalog()}
    assert cat["CL"]["kind"] == "cup" and len(cat) == 41
    assert (
        sources.url_for("CL", "2526")
        == "https://raw.githubusercontent.com/openfootball/champions-league/master/2025-26/cl.txt"
    )
    assert sources.url_for("CONF", "2425").endswith("/2024-25/conf.txt")
    assert sources._allowed(
        "https://raw.githubusercontent.com/openfootball/champions-league/master/2025-26/cl.txt"
    )
    assert not sources._allowed(
        "https://raw.githubusercontent.com/evil/repo/master/x.txt"
    ) and not sources._allowed("http://www.football-data.co.uk/x.csv")


def test_add_cup_downloads_and_follows(db_session, monkeypatch):
    monkeypatch.setattr(sources.time, "sleep", lambda s: None)
    seen = []

    def handler(req):
        seen.append(str(req.url))
        return (
            httpx.Response(404)
            if "2026-27" in str(req.url)
            else httpx.Response(200, content=EXCERPT.encode())
        )

    res = sources.add_league(
        db_session,
        "CL",
        2,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        pause=0,
        today=date(2026, 11, 3),
    )
    assert (
        [r["status"] for r in res] == ["absent", "ok"]
        and res[1]["created"] >= 14
        and len(seen) == 2
    )


# ---------- nouvelles tentatives et diagnostic ----------
def test_fetch_retries_then_reports_a_useful_diagnostic(monkeypatch):
    monkeypatch.setattr(sources.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else httpx.Response(200, text="ok")

    c = httpx.Client(transport=httpx.MockTransport(flaky))
    assert (
        sources.fetch_text("https://www.football-data.co.uk/x.csv", c) == "ok" and calls["n"] == 3
    )
    with pytest.raises(sources.SourceError, match=r"HTTP 503 : www\.football-data\.co\.uk/x\.csv"):
        sources.fetch_text(
            "https://www.football-data.co.uk/x.csv",
            httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))),
        )

    def boom(req):
        raise httpx.ConnectError("no route")

    with pytest.raises(sources.SourceError, match="ConnectError.*Internet"):
        sources.fetch_text(
            "https://www.football-data.co.uk/x.csv",
            httpx.Client(transport=httpx.MockTransport(boom)),
        )


def test_downloaded_file_with_postponed_match_is_no_longer_refused(db_session, monkeypatch):
    """Régression du « championnat refusé » : un seul match reporté (score vide) bloquait tout le fichier."""
    monkeypatch.setattr(sources.time, "sleep", lambda s: None)
    rows = "".join(f"E0,{d:02d}/08/2026,15:00,T{d},U{d},1,0\n" for d in range(1, 21))
    csv_text = (
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG\n"
        + rows
        + "E0,25/08/2026,15:00,Reporte,Aussi,,\n"
    )
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=csv_text)))
    res = sources.add_league(db_session, "E0", 1, client=c, pause=0, today=date(2026, 11, 3))
    assert (
        res[0]["status"] == "ok"
        and res[0]["created"] == 20
        and res[0]["ignored"] == 1
        and "score manquant" in res[0]["ignored_sample"][0]
    )
    assert datetime.now(UTC).year >= 2026


# ---------- cotes de plusieurs bookmakers ----------
FIX = (
    "Div,Date,Time,HomeTeam,AwayTeam,B365H,B365D,B365A,PSH,PSD,PSA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,B365>2.5,B365<2.5,Max>2.5,Max<2.5\n"
    "E0,{d},20:00,Arsenal,Chelsea,1.9,3.5,4.2,1.95,3.6,4.3,2.0,3.7,4.5,1.92,3.5,4.2,1.8,2.0,1.85,2.05\n"
)


def test_fixtures_store_all_bookmakers_and_only_changed_prices(db_session):
    from app.models import Odds
    from app.models.mixins import utcnow
    from app.services.best_odds import best_for_matches

    d = (utcnow() + __import__("datetime").timedelta(days=2)).strftime("%d/%m/%Y")
    r = import_csv(db_session, FIX.format(d=d))
    assert r.created_matches == 1
    n1 = db_session.query(Odds).count()
    assert (
        n1
        == 16  # 4 sources en 1X2 (Bet365, Pinnacle, Max, Moyenne) x 3 + 2 sources en plus/moins 2,5 (Bet365, Max) x 2
    )  # 5 sources 1X2 (Bet365, Pinnacle, Max, Moyenne… = 4 + ...) cf. ci-dessous
    again = import_csv(db_session, FIX.format(d=d))
    assert (
        again.enriched_odds == 0 and db_session.query(Odds).count() == n1
    )  # rien de changé : rien d'ajouté
    changed = import_csv(
        db_session, FIX.format(d=d).replace("1.9,3.5,4.2,1.95", "2.1,3.5,4.2,1.95", 1)
    )
    assert (
        changed.enriched_odds == 1 and db_session.query(Odds).count() == n1 + 1
    )  # un seul prix a changé
    mid = db_session.scalars(select(Match)).one().id
    best = best_for_matches(db_session, [mid])[mid]
    home = best[("1X2", "home", None)]
    assert (
        home["price"] == 2.1 and home["bookmaker"] == "Bet365" and home["bookmakers"] == 4
    )  # la meilleure cote réelle, pas la moyenne
    assert (
        best[("OU", "over", 2.5)]["price"] == 1.85
        and best[("OU", "over", 2.5)]["bookmaker"] == "Meilleure cote du marché"
    )
    assert best[("1X2", "draw", None)]["average"] == pytest.approx(3.5)
