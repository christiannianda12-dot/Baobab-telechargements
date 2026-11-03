from tests.test_odds_api import match  # noqa: F401

REG = {"display_name": "Bob", "password": "motdepasse-solide-1"}


def test_stats_upsert_keeps_missing_as_null(client, auth_headers, match):  # noqa: F811
    url = f"/api/v1/matches/{match['id']}/statistics/{match['home_team_id']}"
    r = client.put(url, json={"corners": 6, "possession_pct": 55.5}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["corners"] == 6 and r.json()["shots"] is None and r.json()["source"] == "manual"
    client.put(url, json={"corners": 7}, headers=auth_headers)  # remplace, pas de doublon
    rows = client.get(f"/api/v1/matches/{match['id']}/statistics").json()
    assert len(rows) == 1 and rows[0]["corners"] == 7 and rows[0]["possession_pct"] is None


def test_stats_validation(client, auth_headers, match):  # noqa: F811
    base = f"/api/v1/matches/{match['id']}/statistics"
    assert client.put(f"{base}/999", json={}, headers=auth_headers).status_code == 422
    url = f"{base}/{match['home_team_id']}"
    assert client.put(url, json={"possession_pct": 130}, headers=auth_headers).status_code == 422
    assert client.put(url, json={"corners": -1}, headers=auth_headers).status_code == 422
    assert client.put(url, json={}).status_code == 401


def test_update_match_result(client, auth_headers, match):  # noqa: F811
    url = f"/api/v1/matches/{match['id']}"
    r = client.patch(
        url, json={"status": "finished", "home_score": 2, "away_score": 1}, headers=auth_headers
    )
    assert r.status_code == 200 and r.json()["status"] == "finished" and r.json()["home_score"] == 2
    half = client.patch(url, json={"home_score": None}, headers=auth_headers)
    assert half.status_code == 422
    assert client.get(url).json()["away_score"] == 1  # annulation propre
    assert client.patch(url, json={"status": "live"}).status_code == 401


def _login(client, email):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": REG["password"]})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_admin_routes_are_protected(client, auth_headers):
    client.post("/api/v1/auth/register", json={**REG, "email": "bob@example.com"})
    bob = _login(client, "bob@example.com")
    assert client.get("/api/v1/admin/users", headers=bob).status_code == 403
    assert client.get("/api/v1/admin/users").status_code == 401
    assert len(client.get("/api/v1/admin/users", headers=auth_headers).json()) == 2


def test_admin_cannot_remove_last_admin_and_can_promote(client, auth_headers):
    client.post("/api/v1/auth/register", json={**REG, "email": "bob@example.com"})
    users = client.get("/api/v1/admin/users", headers=auth_headers).json()
    admin_id = next(u["id"] for u in users if u["role"] == "admin")
    bob_id = next(u["id"] for u in users if u["email"] == "bob@example.com")
    r = client.patch(f"/api/v1/admin/users/{admin_id}", json={"role": "user"}, headers=auth_headers)
    assert r.status_code == 409
    assert (
        client.patch(
            f"/api/v1/admin/users/{bob_id}", json={"role": "admin"}, headers=auth_headers
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/admin/users/{admin_id}", json={"is_active": False}, headers=auth_headers
        ).status_code
        == 200
    )
    # un compte désactivé ne peut plus utiliser son jeton ni se connecter
    assert client.get("/api/v1/auth/me", headers=auth_headers).status_code == 401
    assert (
        client.patch(
            "/api/v1/admin/users/999", json={}, headers=_login(client, "bob@example.com")
        ).status_code
        == 404
    )


def test_provider_sync_reflects_missing_keys(client, auth_headers):
    rows = client.post("/api/v1/admin/providers/sync", headers=auth_headers).json()
    assert {r["code"] for r in rows} == {"api_football", "the_odds_api"}
    assert all(r["is_enabled"] is False for r in rows)
    assert (
        len(client.post("/api/v1/admin/providers/sync", headers=auth_headers).json()) == 2
    )  # idempotent
    assert len(client.get("/api/v1/admin/providers", headers=auth_headers).json()) == 2
