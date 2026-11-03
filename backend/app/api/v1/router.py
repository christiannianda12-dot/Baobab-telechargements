from fastapi import APIRouter

from app.api.v1 import (
    admin,
    assistant,
    auth,
    benchmark,
    combos,
    data,
    dataops,
    health,
    models,
    odds,
    sports,
    stats,
    tracking,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(sports.router)
api_router.include_router(odds.router)
api_router.include_router(stats.router)
api_router.include_router(admin.router)
api_router.include_router(data.router)
api_router.include_router(models.router)
api_router.include_router(tracking.router)
api_router.include_router(combos.router)
api_router.include_router(assistant.router)
api_router.include_router(benchmark.router)
api_router.include_router(dataops.router)
