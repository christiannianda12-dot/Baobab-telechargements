def _setup(client, h):
    comp = client.post(
        "/api/v1/competitions", json={"name": "Ligue Test", "season": "2025-2026"}, headers=h
    ).json()
    a = client.post("/api/v1/teams", json={"name": "Équipe A"}, headers=h).json()
    b = client.post("/api/v1/teams", json={"name": "Équipe B"}, headers=h).json()
    return comp, a, b


def test_writes_require_auth(client):
    assert client.post("/api/v1/teams", json={"name": "X"}).status_code == 401


def test_create_and_list_manual_match(client, auth_headers):
    comp, a, b = _setup(client, auth_headers)
    assert a["source"] == "manual"
    m = client.post(
        "/api/v1/matches",
        headers=auth_headers,
        json={
            "competition_id": comp["id"],
            "home_team_id": a["id"],
            "away_team_id": b["id"],
            "kickoff_at": "2026-11-04T19:00:00Z",
        },
    )
    assert (
        m.status_code == 201
        and m.json()["status"] == "scheduled"
        and m.json()["home_score"] is None
    )
    assert len(client.get("/api/v1/matches").json()) == 1
    assert client.get("/api/v1/matches", params={"date_from": "2026-11-05T00:00:00Z"}).json() == []
    assert client.get(f"/api/v1/matches/{m.json()['id']}").status_code == 200
    assert client.get("/api/v1/matches/999").status_code == 404


def test_match_validation(client, auth_headers):
    comp, a, _ = _setup(client, auth_headers)
    base = {"competition_id": comp["id"], "kickoff_at": "2026-11-04T19:00:00Z"}
    same = client.post(
        "/api/v1/matches",
        headers=auth_headers,
        json={**base, "home_team_id": a["id"], "away_team_id": a["id"]},
    )
    assert same.status_code == 422
    unknown = client.post(
        "/api/v1/matches",
        headers=auth_headers,
        json={**base, "home_team_id": a["id"], "away_team_id": 999},
    )
    assert unknown.status_code == 422
    half = client.post(
        "/api/v1/matches",
        headers=auth_headers,
        json={**base, "home_team_id": a["id"], "away_team_id": 2, "home_score": 1},
    )
    assert half.status_code == 422


def test_duplicate_team_conflict(client, auth_headers):
    client.post("/api/v1/teams", json={"name": "Dup", "country": "FR"}, headers=auth_headers)
    assert (
        client.post(
            "/api/v1/teams", json={"name": "Dup", "country": "FR"}, headers=auth_headers
        ).status_code
        == 409
    )
