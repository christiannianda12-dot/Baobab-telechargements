import io

import pytest

HEAD = "date,competition,season,home_team,away_team,home_score,away_score,home_corners,away_corners,home_possession,away_possession\n"


def _csv(*rows):
    return HEAD + "\n".join(rows) + "\n"


def _post(client, h, text, dry=False):
    return client.post(
        f"/api/v1/import/matches?dry_run={str(dry).lower()}",
        files={"file": ("m.csv", io.BytesIO(text.encode()), "text/csv")},
        headers=h,
    )


GOOD = _csv(
    "2026-01-10,Ligue T,2025-2026,Alpha,Beta,2,1,6,3,55,45",
    "2026-01-20,Ligue T,2025-2026,Beta,Alpha,0,0,,,,",
    "2026-02-01,Ligue T,2025-2026,Alpha,Gamma,3,0,7,,60,",
    "2026-02-10,Ligue T,2025-2026,Gamma,Alpha,1,2,4,5,40,60",
    "2026-03-01,Ligue T,2025-2026,Alpha,Beta,9,9,,,,",  # APRÈS le match analysé
)


def test_import_auth_and_success(client, auth_headers):
    assert _post(client, {}, GOOD).status_code == 401
    r = _post(client, auth_headers, GOOD)
    assert r.status_code == 200
    j = r.json()
    assert j["created_matches"] == 5 and j["created_teams"] == 3 and j["created_competitions"] == 1
    # idempotent : un second import ne crée rien
    j2 = _post(client, auth_headers, GOOD).json()
    assert j2["created_matches"] == 0 and j2["skipped_duplicates"] == 5 and j2["created_teams"] == 0


def test_dry_run_writes_nothing(client, auth_headers):
    j = _post(client, auth_headers, GOOD, dry=True).json()
    assert j["created_matches"] == 5 and j["dry_run"] is True
    assert client.get("/api/v1/matches").json() == []
    assert client.get("/api/v1/teams").json() == []


def test_errors_are_atomic_and_located(client, auth_headers):
    bad = _csv(
        "2026-01-10,L,2025,A,B,2,1,,,,",
        "pas-une-date,L,2025,A,B,2,1,,,,",
        "2026-01-12,L,2025,A,A,1,0,,,,",
        "2026-01-13,L,2025,A,B,-1,0,,,,",
        "2026-01-14,L,2025,A,B,1,0,2.5,,150,",
    )
    r = _post(client, auth_headers, bad)
    assert r.status_code == 422
    d = r.json()["detail"]
    assert [e["line"] for e in d["errors"]] == [3, 4, 5, 6]
    assert client.get("/api/v1/matches").json() == []  # rien d'écrit malgré la ligne 2 valide


def test_bad_header_and_encoding(client, auth_headers):
    r = _post(client, auth_headers, "date,competition\n2026-01-01,L\n")
    assert r.status_code == 422 and "colonnes manquantes" in str(r.json())
    r = _post(client, auth_headers, HEAD.replace("season", "saison") + "x\n")
    assert r.status_code == 422 and "inconnues" in str(r.json())
    r = client.post(
        "/api/v1/import/matches",
        files={"file": ("m.csv", b"\xff\xfe\x00", "text/csv")},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_semicolon_csv(client, auth_headers):
    text = "date;competition;home_team;away_team;home_score;away_score\n2026-01-10;L;A;B;1;0\n"
    assert _post(client, auth_headers, text).json()["created_matches"] == 1


def _target_match(client, h):
    """Match programmé Alpha-Beta le 15/02/2026, après les 4 premiers matchs importés."""
    _post(client, h, GOOD)
    ids = {t["name"]: t["id"] for t in client.get("/api/v1/teams").json()}
    comp = client.get("/api/v1/competitions").json()[0]["id"]
    m = client.post(
        "/api/v1/matches",
        headers=h,
        json={
            "competition_id": comp,
            "home_team_id": ids["Alpha"],
            "away_team_id": ids["Beta"],
            "kickoff_at": "2026-02-15T20:00:00Z",
        },
    )
    return m.json()["id"]


def test_form_excludes_future_and_respects_venue(client, auth_headers):
    mid = _target_match(client, auth_headers)
    a = client.get(f"/api/v1/matches/{mid}/analysis").json()
    alpha = a["home"]["overall"]
    # Alpha avant le 15/02 : 2-1 (D), 0-0 (ext), 3-0 (D), 2-1 ext (V) ; le 9-9 de mars est exclu
    assert (
        alpha["played"] == 4 and alpha["wins"] == 3 and alpha["draws"] == 1 and alpha["losses"] == 0
    )
    assert alpha["goals_for"] == 7 and alpha["goals_against"] == 2
    assert alpha["results"] == ["W", "W", "D", "W"]  # plus récent d'abord
    assert a["home"]["at_home"]["played"] == 2
    assert a["head_to_head"]["played"] == 2 and a["head_to_head"]["team_a_wins"] == 1
    assert a["head_to_head"]["draws"] == 1


def test_missing_stats_are_not_counted_as_zero(client, auth_headers):
    mid = _target_match(client, auth_headers)
    alpha = client.get(f"/api/v1/matches/{mid}/analysis").json()["home"]["overall"]
    # corners d'Alpha : 6 (match 1), 7 (match 3), 5 (match 4) ; le match 2 n'a pas de stats
    assert alpha["averages"]["corners"] == {"average": pytest.approx(6.0), "samples": 3}
    assert alpha["averages"]["possession_pct"]["samples"] == 3
    assert alpha["averages"]["red_cards"] == {"average": None, "samples": 0}


def test_warnings_when_data_is_thin(client, auth_headers):
    mid = _target_match(client, auth_headers)
    a = client.get(f"/api/v1/matches/{mid}/analysis").json()
    assert a["home"]["overall"]["reliable"] is False
    assert any("minimum conseillé" in w for w in a["warnings"])
    assert client.get("/api/v1/matches/999/analysis").status_code == 404
    assert client.get(f"/api/v1/matches/{mid}/analysis?window=1").status_code == 422
