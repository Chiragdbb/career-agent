from app.routers.activity import router as activity_router
from app.routers.applications import router as applications_router
from app.routers.contacts import router as contacts_router
from app.routers.dashboard import router as dashboard_router
from app.routers.documents import analytics_router, documents_router
from app.routers.events import router as events_router
from app.routers.follow_ups import router as follow_ups_router
from app.routers.health import router as health_router
from app.routers.human_tasks import router as human_tasks_router
from app.routers.jobs import router as jobs_router
from app.routers.mailbox import router as mailbox_router
from app.routers.me import router as me_router
from app.routers.notifications import router as notifications_router
from app.routers.outreach import router as outreach_router
from app.routers.pipeline import interviews_router, offers_router
from app.routers.preferences import router as preferences_router
from app.routers.profile import router as profile_router
from app.routers.resumes import router as resumes_router
from app.routers.workflows import router as workflows_router

__all__ = [
    "activity_router",
    "analytics_router",
    "applications_router",
    "contacts_router",
    "dashboard_router",
    "documents_router",
    "events_router",
    "follow_ups_router",
    "health_router",
    "human_tasks_router",
    "interviews_router",
    "jobs_router",
    "mailbox_router",
    "me_router",
    "notifications_router",
    "offers_router",
    "outreach_router",
    "preferences_router",
    "profile_router",
    "resumes_router",
    "workflows_router",
]
