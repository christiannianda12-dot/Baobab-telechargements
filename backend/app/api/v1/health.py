from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbDep
from app.core.config import get_settings
from app.providers.registry import build_providers

router = APIRouter(tags=["système"])


@router.get("/health")
def health(db: DbDep):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@router.get("/system/info")
def system_info():
    s = get_settings()
    return {
        "app": s.app_name,
        "environment": s.environment,
        "data_mode": s.data_mode.value,
        "database": "sqlite" if s.is_sqlite else "postgresql",
        "providers": [
            {"code": p.code, "name": p.name, "kind": p.kind, "configured": p.is_configured}
            for p in build_providers(s)
        ],
    }
