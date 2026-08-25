"""Dashboard / workspace aggregation (read-only, tenant-scoped)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models.enums import HumanTaskStatus
from database.models.schema import (
    Application,
    ApplicationEvent,
    Company,
    CompanyResearch,
    Contact,
    Document,
    EmailVerification,
    FollowUp,
    HumanTask,
    Interview,
    Job,
    JobMatch,
    Offer,
    Outreach,
    Person,
    Resume,
)
from packages.domain.application_strategy import (
    ApplicationStrategy,
    ApplicationStrategyService,
    StrategyInput,
)
from packages.domain.exceptions import NotFoundError
from packages.domain.jobs import JobListingService, JobMatchDetail
from packages.domain.preferences import PreferencesService


class TimelineEvent(BaseModel):
    id: uuid.UUID | None = None
    source: str
    event_type: str
    created_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class DashboardSummary(BaseModel):
    jobs_count: int = 0
    applications_count: int = 0
    open_human_tasks: int = 0
    unread_notifications: int = 0
    upcoming_interviews: int = 0
    pending_offers: int = 0
    open_follow_ups: int = 0
    contacts_count: int = 0
    outreach_count: int = 0
    documents_count: int = 0


class JobWorkspace(BaseModel):
    match: dict[str, Any]
    company_research: dict[str, Any] | None = None
    people: list[dict[str, Any]] = Field(default_factory=list)
    contacts: list[dict[str, Any]] = Field(default_factory=list)
    strategy: ApplicationStrategy | None = None
    application: dict[str, Any] | None = None
    outreach: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)


class ApplicationDetail(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    applied_at: datetime | None = None
    resume_version_id: uuid.UUID | None = None
    cover_letter_document_id: uuid.UUID | None = None
    submission_evidence: dict[str, Any] | None = None
    job_title: str | None = None
    company_name: str | None = None
    events: list[TimelineEvent] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    outreach: list[dict[str, Any]] = Field(default_factory=list)
    follow_ups: list[dict[str, Any]] = Field(default_factory=list)
    human_tasks: list[dict[str, Any]] = Field(default_factory=list)
    interviews: list[dict[str, Any]] = Field(default_factory=list)
    offers: list[dict[str, Any]] = Field(default_factory=list)


class DashboardService:
    """Aggregate SaaS dashboard reads without embedding write business rules."""

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def summary(self) -> DashboardSummary:
        from database.models.enums import FollowUpStatus, NotificationStatus, OfferStatus
        from database.models.schema import Notification

        return DashboardSummary(
            jobs_count=self._count(JobMatch),
            applications_count=self._count(Application),
            open_human_tasks=self._session.query(HumanTask)
            .filter(
                HumanTask.user_id == self._user_id,
                HumanTask.status == HumanTaskStatus.open,
            )
            .count(),
            unread_notifications=self._session.query(Notification)
            .filter(
                Notification.user_id == self._user_id,
                Notification.status == NotificationStatus.unread,
            )
            .count(),
            upcoming_interviews=self._session.query(Interview)
            .filter(Interview.user_id == self._user_id)
            .count(),
            pending_offers=self._session.query(Offer)
            .filter(Offer.user_id == self._user_id, Offer.status == OfferStatus.pending)
            .count(),
            open_follow_ups=self._session.query(FollowUp)
            .filter(
                FollowUp.user_id == self._user_id,
                FollowUp.status.in_(
                    [FollowUpStatus.scheduled, FollowUpStatus.pending_approval]
                ),
            )
            .count(),
            contacts_count=self._count(Contact),
            outreach_count=self._count(Outreach),
            documents_count=self._count(Document),
        )

    def get_job_workspace(self, match_id: uuid.UUID) -> JobWorkspace:
        listing = JobListingService(self._session, self._user_id)
        detail = listing.get_match_detail(match_id)
        match_row = (
            self._session.query(JobMatch, Job, Company)
            .join(Job, Job.id == JobMatch.job_id)
            .join(Company, Company.id == Job.company_id)
            .filter(JobMatch.id == match_id, JobMatch.user_id == self._user_id)
            .one()
        )
        _match, job, company = match_row

        research = (
            self._session.query(CompanyResearch)
            .filter(
                CompanyResearch.user_id == self._user_id,
                CompanyResearch.company_id == company.id,
            )
            .order_by(CompanyResearch.updated_at.desc())
            .first()
        )

        contacts = (
            self._session.query(Contact)
            .filter(Contact.user_id == self._user_id, Contact.company_id == company.id)
            .order_by(Contact.created_at.desc())
            .all()
        )
        people_payload: list[dict[str, Any]] = []
        contact_payload: list[dict[str, Any]] = []
        for c in contacts:
            verifications = (
                self._session.query(EmailVerification)
                .filter(
                    EmailVerification.user_id == self._user_id,
                    EmailVerification.contact_id == c.id,
                )
                .all()
            )
            person = (
                self._session.query(Person).filter(Person.id == c.people_id).one_or_none()
            )
            item = {
                "id": str(c.id),
                "name": c.name,
                "title": c.title,
                "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                "email_verifications": [
                    {
                        "email": v.email,
                        "status": v.status.value
                        if hasattr(v.status, "value")
                        else str(v.status),
                    }
                    for v in verifications
                ],
            }
            contact_payload.append(item)
            people_payload.append(
                {
                    **item,
                    "person_id": str(c.people_id),
                    "person_name": person.name if person else c.name,
                }
            )

        application = (
            self._session.query(Application)
            .filter(Application.user_id == self._user_id, Application.job_id == job.id)
            .one_or_none()
        )
        app_payload = None
        outreach_payload: list[dict[str, Any]] = []
        docs_payload: list[dict[str, Any]] = []
        timeline: list[TimelineEvent] = []
        if application is not None:
            app_payload = {
                "id": str(application.id),
                "status": application.status.value
                if hasattr(application.status, "value")
                else str(application.status),
                "applied_at": application.applied_at.isoformat()
                if application.applied_at
                else None,
                "submission_evidence": application.submission_evidence,
            }
            outreach_payload = self._outreach_for_application(application.id)
            docs_payload = self._documents_for_application(application.id)
            timeline = self._timeline_for_application(application.id)

        prefs = PreferencesService(self._session, self._user_id).get_settings()
        has_resume = (
            self._session.query(Resume)
            .filter(Resume.user_id == self._user_id)
            .count()
            > 0
        )

        strategy = ApplicationStrategyService().build_strategy(
            StrategyInput(
                job_match_id=detail.id,
                job_id=detail.job_id,
                job_title=detail.title,
                company_name=detail.company_name,
                match_score=detail.score,
                match_notes=list(detail.score_breakdown.notes)
                if detail.score_breakdown
                else [],
                company_research_available=research is not None,
                company_research_summary=research.summary if research else None,
                has_canonical_resume=has_resume,
                preferences=prefs,
            )
        )

        return JobWorkspace(
            match=self._match_dict(detail),
            company_research={
                "id": str(research.id),
                "status": research.status.value
                if hasattr(research.status, "value")
                else str(research.status),
                "summary": research.summary,
                "data": research.data if isinstance(research.data, dict) else {},
            }
            if research
            else None,
            people=people_payload,
            contacts=contact_payload,
            strategy=strategy,
            application=app_payload,
            outreach=outreach_payload,
            documents=docs_payload,
            timeline=timeline,
        )

    def get_application_detail(self, application_id: uuid.UUID) -> ApplicationDetail:
        row = (
            self._session.query(Application, Job, Company)
            .join(Job, Job.id == Application.job_id)
            .join(Company, Company.id == Job.company_id)
            .filter(Application.id == application_id, Application.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Application not found")
        application, job, company = row

        interviews = (
            self._session.query(Interview)
            .filter(
                Interview.user_id == self._user_id,
                Interview.application_id == application_id,
            )
            .order_by(Interview.scheduled_at.desc().nullslast())
            .all()
        )
        offers = (
            self._session.query(Offer)
            .filter(Offer.user_id == self._user_id, Offer.application_id == application_id)
            .order_by(Offer.created_at.desc())
            .all()
        )
        follow_ups = (
            self._session.query(FollowUp)
            .filter(
                FollowUp.user_id == self._user_id,
                FollowUp.application_id == application_id,
            )
            .order_by(FollowUp.next_action_at.asc())
            .all()
        )
        tasks = (
            self._session.query(HumanTask)
            .filter(
                HumanTask.user_id == self._user_id,
                HumanTask.application_id == application_id,
            )
            .order_by(HumanTask.created_at.desc())
            .all()
        )

        return ApplicationDetail(
            id=application.id,
            job_id=application.job_id,
            status=application.status.value
            if hasattr(application.status, "value")
            else str(application.status),
            applied_at=application.applied_at,
            resume_version_id=application.resume_version_id,
            cover_letter_document_id=application.cover_letter_document_id,
            submission_evidence=application.submission_evidence
            if isinstance(application.submission_evidence, dict)
            else None,
            job_title=job.title,
            company_name=company.name,
            events=self._timeline_for_application(application_id),
            documents=self._documents_for_application(application_id),
            outreach=self._outreach_for_application(application_id),
            follow_ups=[
                {
                    "id": str(f.id),
                    "status": f.status.value if hasattr(f.status, "value") else str(f.status),
                    "next_action_at": f.next_action_at.isoformat()
                    if f.next_action_at
                    else None,
                    "subject": f.subject,
                }
                for f in follow_ups
            ],
            human_tasks=[
                {
                    "id": str(t.id),
                    "task_type": t.task_type,
                    "title": t.title,
                    "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                }
                for t in tasks
            ],
            interviews=[
                {
                    "id": str(i.id),
                    "status": i.status.value if hasattr(i.status, "value") else str(i.status),
                    "title": i.title,
                    "round": i.round,
                    "format": i.format,
                    "interviewer": i.interviewer,
                    "scheduled_at": i.scheduled_at.isoformat() if i.scheduled_at else None,
                }
                for i in interviews
            ],
            offers=[
                {
                    "id": str(o.id),
                    "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                    "offer_deadline": o.offer_deadline.isoformat()
                    if o.offer_deadline
                    else None,
                    "details": o.details if isinstance(o.details, dict) else {},
                }
                for o in offers
            ],
        )

    def list_documents(self) -> list[dict[str, Any]]:
        rows = (
            self._session.query(Document)
            .filter(Document.user_id == self._user_id)
            .order_by(Document.created_at.desc())
            .all()
        )
        return [
            {
                "id": str(d.id),
                "filename": d.filename,
                "mime_type": d.mime_type,
                "status": d.status.value if hasattr(d.status, "value") else str(d.status),
                "application_id": str(d.application_id) if d.application_id else None,
                "resume_version_id": str(d.resume_version_id)
                if d.resume_version_id
                else None,
            }
            for d in rows
        ]

    def list_applications_enriched(self) -> list[dict[str, Any]]:
        rows = (
            self._session.query(Application, Job, Company)
            .join(Job, Job.id == Application.job_id)
            .join(Company, Company.id == Job.company_id)
            .filter(Application.user_id == self._user_id)
            .order_by(Application.created_at.desc())
            .all()
        )
        return [
            {
                "id": str(app.id),
                "job_id": str(app.job_id),
                "status": app.status.value if hasattr(app.status, "value") else str(app.status),
                "job_title": job.title,
                "company_name": company.name,
                "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            }
            for app, job, company in rows
        ]

    def _count(self, model: type) -> int:
        return (
            self._session.query(model).filter(model.user_id == self._user_id).count()  # type: ignore[attr-defined]
        )

    def _outreach_for_application(self, application_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            self._session.query(Outreach)
            .filter(
                Outreach.user_id == self._user_id,
                Outreach.application_id == application_id,
            )
            .order_by(Outreach.created_at.desc())
            .all()
        )
        return [
            {
                "id": str(o.id),
                "contact_id": str(o.contact_id),
                "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                "subject": o.subject,
            }
            for o in rows
        ]

    def _documents_for_application(self, application_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            self._session.query(Document)
            .filter(
                Document.user_id == self._user_id,
                Document.application_id == application_id,
            )
            .order_by(Document.created_at.desc())
            .all()
        )
        return [
            {
                "id": str(d.id),
                "filename": d.filename,
                "status": d.status.value if hasattr(d.status, "value") else str(d.status),
                "mime_type": d.mime_type,
            }
            for d in rows
        ]

    def _timeline_for_application(self, application_id: uuid.UUID) -> list[TimelineEvent]:
        events = (
            self._session.query(ApplicationEvent)
            .filter(
                ApplicationEvent.user_id == self._user_id,
                ApplicationEvent.application_id == application_id,
            )
            .order_by(ApplicationEvent.created_at.desc())
            .all()
        )
        return [
            TimelineEvent(
                id=e.id,
                source="application_event",
                event_type=e.event_type,
                created_at=e.created_at,
                payload=e.payload if isinstance(e.payload, dict) else {},
            )
            for e in events
        ]

    @staticmethod
    def _match_dict(detail: JobMatchDetail) -> dict[str, Any]:
        breakdown = None
        if detail.score_breakdown is not None:
            b = detail.score_breakdown
            breakdown = {
                "total": b.total,
                "role": b.role,
                "location": b.location,
                "work_arrangement": b.work_arrangement,
                "salary": b.salary,
                "skills": b.skills,
                "seniority": b.seniority,
                "notes": list(b.notes),
            }
        return {
            "id": str(detail.id),
            "job_id": str(detail.job_id),
            "status": detail.status,
            "score": detail.score,
            "title": detail.title,
            "company_name": detail.company_name,
            "location": detail.location,
            "work_arrangement": detail.work_arrangement,
            "url": detail.url,
            "description": detail.description,
            "job_skills": detail.job_skills,
            "matched_skills": detail.matched_skills,
            "missing_skills": detail.missing_skills,
            "score_breakdown": breakdown,
            "explanation": detail.explanation,
            "created_at": detail.created_at.isoformat() if detail.created_at else None,
        }
