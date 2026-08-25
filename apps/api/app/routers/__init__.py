from app.routers.applications import router as applications_router
from app.routers.contacts import router as contacts_router
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
from app.routers.me import router as me_router
from app.routers.outreach import router as outreach_router
from app.routers.preferences import router as preferences_router
from app.routers.profile import router as profile_router
from app.routers.resumes import router as resumes_router
from app.routers.workflows import router as workflows_router

from app.routers.workflows import router as workflows_router

__all__ = [
    "applications_router",
    "contacts_router",
    "health_router",
    "jobs_router",
    "me_router",
    "outreach_router",
    "preferences_router",
    "profile_router",
    "resumes_router",
    "workflows_router",
]
