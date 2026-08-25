from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.database import init_db
from app.middleware import CorrelationIdMiddleware, register_exception_handlers
from app.redis import close_redis, init_redis
from app.routers import (
    applications_router,
    contacts_router,
    health_router,
    jobs_router,
    me_router,
    outreach_router,
    preferences_router,
    profile_router,
    resumes_router,
    workflows_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    init_db(settings)
    init_redis(settings)
    yield
    close_redis()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory for the Career Agent API."""
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Local Next.js (apps/web) calls the API with a Bearer token from the browser.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(app)

    prefix = settings.api_v1_prefix
    app.include_router(health_router, prefix=prefix)
    app.include_router(me_router, prefix=prefix)
    app.include_router(profile_router, prefix=prefix)
    app.include_router(preferences_router, prefix=prefix)
    app.include_router(jobs_router, prefix=prefix)
    app.include_router(applications_router, prefix=prefix)
    app.include_router(resumes_router, prefix=prefix)
    app.include_router(contacts_router, prefix=prefix)
    app.include_router(outreach_router, prefix=prefix)
    app.include_router(workflows_router, prefix=prefix)

    return app


app = create_app()
