from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=f"{s.app_name} API",
        version="0.1.0",
        docs_url="/docs" if s.environment != "production" else None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(api_router)
    return app


app = create_app()
