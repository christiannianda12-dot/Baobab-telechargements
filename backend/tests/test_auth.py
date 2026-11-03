from app.core.security import hash_password, verify_password

REG = {"email": "a@example.com", "display_name": "Alice", "password": "motdepasse-solide-1"}


def test_password_hash_is_not_plaintext():
    h = hash_password("secret-secret")
    assert h != "secret-secret" and verify_password("secret-secret", h)
    assert not verify_password("autre", h)


def test_register_login_me_and_first_user_is_admin(client):
    r = client.post("/api/v1/auth/register", json=REG)
    assert r.status_code == 201 and r.json()["role"] == "admin"
    assert "password" not in r.text and "hashed" not in r.text
    r2 = client.post("/api/v1/auth/register", json={**REG, "email": "b@example.com"})
    assert r2.json()["role"] == "user"
    tok = client.post(
        "/api/v1/auth/login", data={"username": "A@example.com", "password": REG["password"]}
    ).json()
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == "a@example.com"


def test_duplicate_and_weak_password_rejected(client):
    client.post("/api/v1/auth/register", json=REG)
    assert client.post("/api/v1/auth/register", json=REG).status_code == 409
    assert (
        client.post(
            "/api/v1/auth/register", json={**REG, "email": "c@example.com", "password": "court"}
        ).status_code
        == 422
    )


def test_bad_credentials_and_bad_token(client):
    client.post("/api/v1/auth/register", json=REG)
    assert (
        client.post(
            "/api/v1/auth/login", data={"username": REG["email"], "password": "faux-faux-faux"}
        ).status_code
        == 401
    )
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    )
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_rate_limited(client):
    codes = [
        client.post(
            "/api/v1/auth/login", data={"username": "x@example.com", "password": "yyyyyyyyyy"}
        ).status_code
        for _ in range(12)
    ]
    assert codes[0] == 401 and codes[-1] == 429
