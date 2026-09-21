"""Career Agent MCP server — thin tool surface over domain services.

No business logic, scraping, browser automation, vendor SDKs, or raw SQL
CRUD lives here. Auth/approval/audit are enforced by the same domain services
used by the HTTP API.

Auth (see mcp/context.py):
  MCP_USER_ID | MCP_AUTH_SUBJECT | MCP_AUTH_TOKEN

Legacy CRUD tools were moved to mcp/legacy_server.py and are not registered.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

# Repo root must be on sys.path for `packages.*` / `apps/api` imports, but must
# not shadow the installed MCP SDK (`mcp` package). Append, do not insert.
_MCP_DIR = Path(__file__).resolve().parent
_ROOT = _MCP_DIR.parent
for _path in (_MCP_DIR, _ROOT / "apps" / "api", _ROOT):
    _s = str(_path)
    if _s not in sys.path:
        sys.path.append(_s)

from mcp.server.fastmcp import FastMCP

# Local helpers live beside this file; they are not part of the MCP SDK.
from context import mcp_session, resolve_mcp_user_id

mcp = FastMCP("career-agent")


def _json(data: Any) -> str:
    return json.dumps(data, default=str)


@mcp.tool()
def search_jobs(include_dismissed: bool = False) -> str:
    """List tenant job matches (same as dashboard jobs list)."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.jobs import JobListingService

        rows = JobListingService(session, user_id).list_matches(
            include_dismissed=include_dismissed
        )
        return _json([r.__dict__ for r in rows])


@mcp.tool()
def get_job(match_id: str) -> str:
    """Get a job match detail by match id (tenant-scoped)."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.jobs import JobListingService

        detail = JobListingService(session, user_id).get_match_detail(uuid.UUID(match_id))
        return _json(detail.__dict__)


@mcp.tool()
def score_job(match_id: str) -> str:
    """Re-score a job match using JobMatchService (deterministic + optional semantic)."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.jobs import JobListingService
        from packages.domain.job_match import JobMatchService
        from packages.providers.factory import create_embedding_provider

        listing = JobListingService(session, user_id)
        detail = listing.get_match_detail(uuid.UUID(match_id))
        matcher = JobMatchService(session, user_id, embedding=create_embedding_provider())
        row = matcher.upsert_match(detail.job_id)
        return _json(
            {
                "match_id": str(row.id),
                "job_id": str(row.job_id),
                "score": row.score,
                "semantic_score": row.semantic_score,
                "scoring_algorithm_version": row.scoring_algorithm_version,
                "fit_summary": row.fit_summary,
            }
        )


@mcp.tool()
def research_company(job_id: str, force_refresh: bool = False) -> str:
    """Run CompanyResearchService for a job's company."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.company_research import CompanyResearchService
        from packages.domain.llm_tasks import LLMTaskService
        from packages.providers.factory import (
            create_llm_provider,
            create_scraper_provider,
            create_search_provider,
        )

        llm = create_llm_provider()
        service = CompanyResearchService(
            session,
            user_id,
            search=create_search_provider(),
            scraper=create_scraper_provider(),
            llm_tasks=LLMTaskService(llm),
        )
        row = service.research_for_job(uuid.UUID(job_id), force_refresh=force_refresh)
        return _json(
            {
                "id": str(row.id),
                "company_id": str(row.company_id),
                "status": row.status.value if hasattr(row.status, "value") else str(row.status),
                "summary": row.summary,
                "data": row.data,
            }
        )


@mcp.tool()
def find_people(job_id: str) -> str:
    """Discover people for a job via PeopleResearchService."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.people_research import PeopleResearchService
        from packages.providers.factory import (
            create_email_finder_provider,
            create_email_verifier_provider,
            create_people_provider,
        )

        service = PeopleResearchService(
            session,
            user_id,
            people=create_people_provider(),
            email_finder=create_email_finder_provider(),
            email_verifier=create_email_verifier_provider(),
        )
        result = service.research_for_job(uuid.UUID(job_id))
        return _json(result.model_dump() if hasattr(result, "model_dump") else result)


@mcp.tool()
def find_contacts(job_id: str | None = None) -> str:
    """List tenant contacts (tenant-scoped; job_id reserved for future filter)."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from database.models.schema import Contact, EmailVerification

        _ = job_id  # reserved; contacts are tenant-scoped
        rows = (
            session.query(Contact)
            .filter(Contact.user_id == user_id)
            .order_by(Contact.created_at.desc())
            .limit(50)
            .all()
        )
        out = []
        for r in rows:
            ev = (
                session.query(EmailVerification)
                .filter(
                    EmailVerification.user_id == user_id,
                    EmailVerification.contact_id == r.id,
                )
                .order_by(EmailVerification.created_at.desc())
                .first()
            )
            out.append(
                {
                    "id": str(r.id),
                    "people_id": str(r.people_id) if r.people_id else None,
                    "name": r.name,
                    "title": r.title,
                    "email": ev.email if ev else None,
                    "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                }
            )
        return _json(out)


@mcp.tool()
def generate_resume(match_id: str, resume_id: str | None = None) -> str:
    """Customize resume for a match via ResumeCustomizationService (no fabrication)."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from database.models.schema import Resume
        from packages.domain.resume_customization import ResumeCustomizationService

        if resume_id:
            rid = uuid.UUID(resume_id)
        else:
            resume = (
                session.query(Resume)
                .filter(Resume.user_id == user_id)
                .order_by(Resume.created_at.desc())
                .first()
            )
            if resume is None:
                return _json({"error": "No resume available"})
            rid = resume.id
        version = ResumeCustomizationService(session, user_id).customize_for_match(
            resume_id=rid,
            job_match_id=uuid.UUID(match_id),
        )
        return _json(
            {
                "resume_version_id": str(version.id),
                "resume_id": str(version.resume_id),
                "status": version.status.value
                if hasattr(version.status, "value")
                else str(version.status),
            }
        )


@mcp.tool()
def generate_cover_letter(match_id: str) -> str:
    """Generate a cover letter draft via ApplicationContentService."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.application_content import ApplicationContentService
        from packages.domain.jobs import JobListingService
        from packages.domain.resume_models import StructuredResume
        from packages.prompts.application_content import ContentPromptKind
        from packages.providers.factory import create_llm_provider
        from database.models.schema import ResumeVersion

        detail = JobListingService(session, user_id).get_match_detail(uuid.UUID(match_id))
        version = (
            session.query(ResumeVersion)
            .filter(ResumeVersion.user_id == user_id)
            .order_by(ResumeVersion.created_at.desc())
            .first()
        )
        if version is None or not version.sections:
            return _json({"error": "No structured resume available"})
        structured = StructuredResume.model_validate(version.sections)
        service = ApplicationContentService(create_llm_provider())
        generated = service.generate(
            ContentPromptKind.cover_letter,
            structured_resume=structured,
            job={"title": detail.title, "description": detail.description},
            company={"name": detail.company_name},
            user_id=user_id,
            job_id=detail.job_id,
            resume_version_id=version.id,
        )
        return _json(generated.model_dump())


@mcp.tool()
def prepare_application(job_id: str, resume_version_id: str | None = None) -> str:
    """Create/return a PREPARED application (never SUBMITTED)."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.application_engine import ApplicationEngine

        app = ApplicationEngine(session, user_id).prepare(
            uuid.UUID(job_id),
            resume_version_id=uuid.UUID(resume_version_id) if resume_version_id else None,
        )
        return _json(
            {
                "application_id": str(app.id),
                "job_id": str(app.job_id),
                "status": app.status.value if hasattr(app.status, "value") else str(app.status),
                "engine_status": (app.submission_evidence or {}).get("engine_status"),
            }
        )


@mcp.tool()
def submit_application(application_id: str, confirmation_id: str = "") -> str:
    """Transition to SUBMITTED only when explicit evidence is provided."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.application_engine import ApplicationEngine, EngineState
        from packages.domain.exceptions import DomainError

        if not (confirmation_id or "").strip():
            raise DomainError("submit_application requires confirmation_id evidence")
        engine = ApplicationEngine(session, user_id)
        state = engine.get_state(uuid.UUID(application_id))
        if state == EngineState.PREPARED:
            engine.transition(
                uuid.UUID(application_id),
                EngineState.AWAITING_APPROVAL,
                reason="mcp_submit_requested",
                actor="mcp",
            )
            engine.transition(
                uuid.UUID(application_id),
                EngineState.IN_PROGRESS,
                reason="mcp_approved",
                actor="mcp",
            )
        elif state == EngineState.AWAITING_APPROVAL:
            engine.transition(
                uuid.UUID(application_id),
                EngineState.IN_PROGRESS,
                reason="mcp_approved",
                actor="mcp",
            )
        result = engine.transition(
            uuid.UUID(application_id),
            EngineState.SUBMITTED,
            evidence={"confirmation_id": confirmation_id.strip()},
            actor="mcp",
        )
        return _json(result.model_dump())


@mcp.tool()
def draft_outreach(
    contact_id: str,
    subject: str,
    body: str,
    reason: str = "mcp_draft",
    outreach_type: str = "recruiter",
    application_id: str | None = None,
) -> str:
    """Draft outreach via OutreachService (approval still required to send)."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.outreach import OutreachDraftInput, OutreachService, OutreachType
        from packages.providers.factory import create_email_sender_provider

        service = OutreachService(
            session, user_id, email_sender=create_email_sender_provider()
        )
        view = service.create_draft(
            OutreachDraftInput(
                contact_id=uuid.UUID(contact_id),
                outreach_type=OutreachType(outreach_type),
                subject=subject,
                body=body,
                reason=reason,
                application_id=uuid.UUID(application_id) if application_id else None,
                request_approval=True,
            )
        )
        return _json(view.model_dump())


@mcp.tool()
def send_outreach(outreach_id: str) -> str:
    """Send outreach only if already approved / automation allows (OutreachService)."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.outreach import OutreachService
        from packages.providers.factory import create_email_sender_provider

        service = OutreachService(
            session, user_id, email_sender=create_email_sender_provider()
        )
        view = service.send(uuid.UUID(outreach_id))
        return _json(view.model_dump())


@mcp.tool()
def get_application(application_id: str) -> str:
    """Get application detail via DashboardService."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.dashboard import DashboardService

        detail = DashboardService(session, user_id).get_application_detail(
            uuid.UUID(application_id)
        )
        return _json(detail.model_dump())


@mcp.tool()
def get_dashboard_summary() -> str:
    """Dashboard summary counts for the authenticated tenant."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.dashboard import DashboardService

        return _json(DashboardService(session, user_id).summary().model_dump())


@mcp.tool()
def list_human_tasks(include_resolved: bool = False) -> str:
    """List human tasks for the authenticated tenant."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from database.models.enums import HumanTaskStatus
        from packages.domain.human_tasks import HumanTaskService

        status = None if include_resolved else HumanTaskStatus.open
        rows = HumanTaskService(session, user_id).list_tasks(status=status)
        return _json([r.model_dump() for r in rows])


@mcp.tool()
def resolve_human_task(
    task_id: str,
    notes: str = "",
    resume_workflow: bool = True,
) -> str:
    """Resolve a human task via HumanTaskService."""
    with mcp_session() as session:
        user_id = resolve_mcp_user_id(session)
        from packages.domain.human_tasks import HumanTaskResolveInput, HumanTaskService

        view = HumanTaskService(session, user_id).resolve(
            uuid.UUID(task_id),
            HumanTaskResolveInput(
                notes=notes or None,
                resolution={},
                resume_workflow=resume_workflow,
            ),
        )
        return _json(view.model_dump())


if __name__ == "__main__":
    mcp.run()
