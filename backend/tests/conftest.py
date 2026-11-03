import os

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-0123456789"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.rate_limit import reset_rate_limits  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db, make_engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def db_session():
    """SQLite en mémoire par défaut ; PostgreSQL si TEST_DATABASE_URL est défini."""
    url = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    engine = make_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    reset_rate_limits()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@example.com",
            "display_name": "Admin",
            "password": "motdepasse-solide-1",
        },
    )
    r = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@example.com", "password": "motdepasse-solide-1"},
    )
    client.cookies.clear()  # les tests passent l'en-tête explicitement ; le cookie a ses tests dédiés
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
