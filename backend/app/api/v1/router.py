from fastapi import APIRouter

from app.api.v1 import admin, auth, health, odds, sports, stats

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(sports.router)
api_router.include_router(odds.router)
api_router.include_router(stats.router)
api_router.include_router(admin.router)
