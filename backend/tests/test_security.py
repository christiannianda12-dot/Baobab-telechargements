import pytest

from app.core.config import Settings

REG = {"email": "s@example.com", "display_name": "Sec", "password": "motdepasse-solide-1"}
OK_ORIGIN = {"Origin": "http://localhost:3000"}


def _login(client):
    client.post("/api/v1/auth/register", json=REG)
    return client.post(
        "/api/v1/auth/login", data={"username": REG["email"], "password": REG["password"]}
    )


def test_login_sets_httponly_session_cookie(client):
    r = _login(client)
    assert r.status_code == 200
    c = r.headers["set-cookie"].lower()
    assert "predix_session=" in c and "httponly" in c and "samesite=lax" in c
    assert "secure" not in c.replace("samesite", "")  # développement en HTTP


def test_cookie_alone_authenticates_and_logout_clears_it(client):
    _login(client)
    assert client.get("/api/v1/auth/me").json()["email"] == REG["email"]
    assert client.post("/api/v1/auth/logout", headers=OK_ORIGIN).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_csrf_origin_check_on_cookie_authenticated_writes(client):
    _login(client)
    body = {"name": "Équipe CSRF"}
    assert client.post("/api/v1/teams", json=body).status_code == 403  # pas d'origine
    assert (
        client.post(
            "/api/v1/teams", json=body, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert client.post("/api/v1/teams", json=body, headers=OK_ORIGIN).status_code == 201
    assert client.get("/api/v1/teams").status_code == 200  # lecture non concernée


def test_bearer_clients_are_not_subject_to_origin_check(client):
    r = _login(client)
    token = r.json()["access_token"]
    client.cookies.clear()
    ok = client.post(
        "/api/v1/teams", json={"name": "Via Bearer"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert ok.status_code == 201


def test_forged_cookie_is_rejected(client):
    client.cookies.set("predix_session", "forged.token.value")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_security_headers_and_no_store(client):
    r = client.get("/api/v1/health")
    assert (
        r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    )
    assert (
        r.headers["referrer-policy"] == "no-referrer" and r.headers["cache-control"] == "no-store"
    )
    assert "strict-transport-security" not in r.headers  # HSTS uniquement en production


def test_cors_allows_credentials_only_for_configured_origin(client):
    ok = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert (
        ok.headers["access-control-allow-origin"] == "http://localhost:3000"
        and ok.headers["access-control-allow-credentials"] == "true"
    )
    bad = client.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers


def test_production_config_is_strict():
    good = dict(
        environment="production", secret_key="x" * 40, cors_origins="https://app.example.com"
    )
    s = Settings(**good)
    assert s.cookie_secure_effective is True
    for bad in (
        {"secret_key": "court"},
        {"cors_origins": "*"},
        {"cors_origins": "http://localhost:3000"},
    ):
        with pytest.raises(ValueError):
            Settings(**{**good, **bad})
    assert Settings(environment="development").cookie_secure_effective is False


def test_lan_origins_only_when_explicitly_enabled(client, monkeypatch):
    _login(client)
    lan = {"Origin": "http://192.168.1.50:3000"}
    assert (
        client.post("/api/v1/teams", json={"name": "LAN 1"}, headers=lan).status_code == 403
    )  # désactivé par défaut
    import app.core.middleware as mw

    monkeypatch.setattr(
        mw, "get_settings", lambda: Settings(environment="development", allow_lan_origins=True)
    )
    assert client.post("/api/v1/teams", json={"name": "LAN 2"}, headers=lan).status_code == 201
    for bad in (
        "http://8.8.8.8:3000",
        "https://evil.example",
        "http://192.168.1.50:8080",
        "http://192.168.1.50.evil.com:3000",
    ):
        assert (
            client.post("/api/v1/teams", json={"name": bad}, headers={"Origin": bad}).status_code
            == 403
        )


def test_lan_mode_is_forbidden_in_production():
    with pytest.raises(ValueError):
        Settings(
            environment="production",
            secret_key="x" * 40,
            cors_origins="https://a.example.com",
            allow_lan_origins=True,
        )
