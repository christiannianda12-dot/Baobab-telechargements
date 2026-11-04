import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.middleware import OriginCheckMiddleware, SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    task = None
    if s.scheduler_enabled and s.environment != "test":
        from app.db.session import SessionLocal
        from app.services import scheduler

        task = asyncio.create_task(scheduler.loop(SessionLocal))
    yield
    if task:
        task.cancel()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        lifespan=lifespan,
        title=f"{s.app_name} API",
        version="0.1.0",
        docs_url="/docs" if s.environment != "production" else None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_origin_regex=s.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(OriginCheckMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(api_router)
    return app


app = create_app()
