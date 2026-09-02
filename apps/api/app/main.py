from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.database import init_db
from app.middleware import CorrelationIdMiddleware, register_exception_handlers
from app.redis import close_redis, init_redis
from packages.shared.env import load_project_env
from packages.shared.logging import configure_logging
from packages.providers.factory import log_active_providers

load_project_env()
from app.routers import (
    activity_router,
    analytics_router,
    applications_router,
    contacts_router,
    dashboard_router,
    documents_router,
    events_router,
    follow_ups_router,
    health_router,
    human_tasks_router,
    interviews_router,
    jobs_router,
    mailbox_router,
    me_router,
    notifications_router,
    offers_router,
    outreach_router,
    preferences_router,
    profile_router,
    resumes_router,
    workflows_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_project_env()
    settings: Settings = app.state.settings
    configure_logging(level="DEBUG" if settings.app_env == "development" else "INFO")
    log_active_providers()
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

    # Browser clients (apps/web) call the API with a Bearer token.
    # Origins come from CORS_ALLOW_ORIGINS (comma-separated).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
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
    app.include_router(activity_router, prefix=prefix)
    app.include_router(applications_router, prefix=prefix)
    app.include_router(resumes_router, prefix=prefix)
    app.include_router(contacts_router, prefix=prefix)
    app.include_router(outreach_router, prefix=prefix)
    app.include_router(human_tasks_router, prefix=prefix)
    app.include_router(mailbox_router, prefix=prefix)
    app.include_router(workflows_router, prefix=prefix)
    app.include_router(dashboard_router, prefix=prefix)
    app.include_router(events_router, prefix=prefix)
    app.include_router(notifications_router, prefix=prefix)
    app.include_router(follow_ups_router, prefix=prefix)
    app.include_router(interviews_router, prefix=prefix)
    app.include_router(offers_router, prefix=prefix)
    app.include_router(documents_router, prefix=prefix)
    app.include_router(analytics_router, prefix=prefix)

    return app


app = create_app()
