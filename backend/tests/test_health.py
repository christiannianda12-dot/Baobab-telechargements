def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "database": "ok"}


def test_system_info_providers_disabled_without_keys(client):
    info = client.get("/api/v1/system/info").json()
    assert info["data_mode"] == "manual"
    assert {p["code"] for p in info["providers"]} == {"api_football", "the_odds_api"}
    assert all(p["configured"] is False for p in info["providers"])
