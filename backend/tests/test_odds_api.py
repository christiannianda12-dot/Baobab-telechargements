import pytest


@pytest.fixture
def match(client, auth_headers):
    comp = client.post("/api/v1/competitions", json={"name": "L"}, headers=auth_headers).json()
    a = client.post("/api/v1/teams", json={"name": "A"}, headers=auth_headers).json()
    b = client.post("/api/v1/teams", json={"name": "B"}, headers=auth_headers).json()
    m = client.post(
        "/api/v1/matches",
        headers=auth_headers,
        json={
            "competition_id": comp["id"],
            "home_team_id": a["id"],
            "away_team_id": b["id"],
            "kickoff_at": "2026-11-04T19:00:00Z",
        },
    ).json()
    return m


def _odds(client, h, mid, sel, price, market="1X2", **kw):
    body = {"bookmaker": "Manuel", "market": market, "selection": sel, "price": price, **kw}
    return client.post(f"/api/v1/matches/{mid}/odds", json=body, headers=h)


def test_no_odds_means_no_analysis(client, match):
    assert client.get(f"/api/v1/matches/{match['id']}/odds").json() == []
    assert client.get(f"/api/v1/matches/{match['id']}/odds/analysis").json()["markets"] == []


def test_odds_require_auth_and_valid_match(client, auth_headers, match):
    assert client.post(f"/api/v1/matches/{match['id']}/odds", json={}).status_code == 401
    assert _odds(client, auth_headers, 999, "home", 2.0).status_code == 404


@pytest.mark.parametrize(
    "kw",
    [
        {"sel": "home", "price": 1.0},  # cote <= 1
        {"sel": "over", "price": 2.0},  # mauvaise sélection pour 1X2
        {"sel": "over", "price": 2.0, "market": "OU"},  # ligne manquante
        {"sel": "home", "price": 2.0, "line": 2.5},  # ligne interdite pour 1X2
    ],
)
def test_odds_validation(client, auth_headers, match, kw):
    sel, price = kw.pop("sel"), kw.pop("price")
    assert _odds(client, auth_headers, match["id"], sel, price, **kw).status_code == 422


def test_analysis_complete_1x2_removes_margin(client, auth_headers, match):
    for sel, price in (("home", 2.10), ("draw", 3.40), ("away", 3.60)):
        assert _odds(client, auth_headers, match["id"], sel, price).status_code == 201
    mk = client.get(f"/api/v1/matches/{match['id']}/odds/analysis").json()["markets"]
    assert len(mk) == 1 and mk[0]["complete"] is True
    over = 1 / 2.10 + 1 / 3.40 + 1 / 3.60
    assert mk[0]["margin"] == pytest.approx(over - 1)
    assert sum(mk[0]["fair_probabilities"].values()) == pytest.approx(1.0)
    assert mk[0]["selections"]["home"]["implied_probability"] == pytest.approx(1 / 2.10)


def test_incomplete_market_has_no_fair_probabilities(client, auth_headers, match):
    _odds(client, auth_headers, match["id"], "home", 2.0)
    mk = client.get(f"/api/v1/matches/{match['id']}/odds/analysis").json()["markets"][0]
    assert mk["complete"] is False and mk["fair_probabilities"] is None and mk["margin"] is None


def test_latest_odds_win_and_history_kept(client, auth_headers, match):
    _odds(client, auth_headers, match["id"], "over", 1.90, market="OU", line=2.5)
    _odds(client, auth_headers, match["id"], "over", 2.00, market="OU", line=2.5)
    _odds(client, auth_headers, match["id"], "under", 1.90, market="OU", line=2.5)
    assert len(client.get(f"/api/v1/matches/{match['id']}/odds").json()) == 3
    mk = client.get(f"/api/v1/matches/{match['id']}/odds/analysis").json()["markets"][0]
    assert mk["selections"]["over"]["price"] == 2.0 and mk["complete"]


def test_calculate_endpoint(client):
    r = client.post(
        "/api/v1/odds/calculate",
        json={"prices": [2.0, 2.0], "estimated_probabilities": [0.55, 0.45]},
    ).json()
    assert r["margin"] == pytest.approx(0.0)
    assert r["expected_values"] == pytest.approx([0.10, -0.10])
    assert client.post("/api/v1/odds/calculate", json={"prices": [0.9, 2.0]}).status_code == 422
    bad = {"prices": [2.0, 2.0], "estimated_probabilities": [0.5]}
    assert client.post("/api/v1/odds/calculate", json=bad).status_code == 422
