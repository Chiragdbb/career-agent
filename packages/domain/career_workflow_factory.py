"""Build CareerWorkflowService with real step injectors (wire-first)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from database.models.schema import Contact, Job, JobMatch, Resume, ResumeVersion
from packages.domain.application_content import ApplicationContentService
from packages.domain.ats_score import AtsScoreService
from packages.domain.career_workflow import CareerWorkflowService
from packages.domain.events import UserEventPublisher
from packages.domain.outreach import OutreachDraftInput, OutreachService, OutreachType
from packages.domain.resume_customization import ResumeCustomizationService
from packages.domain.resume_models import StructuredResume
from packages.domain.workflow_progress import WorkflowProgressService
from packages.prompts.application_content import ContentPromptKind
from packages.providers.factory import create_llm_provider
from packages.providers.notification import NotificationProvider


def build_career_workflow_service(
    session: Session,
    user_id: uuid.UUID,
    *,
    events: UserEventPublisher | None = None,
    notifications: NotificationProvider | None = None,
) -> CareerWorkflowService:
    progress = WorkflowProgressService(session, user_id, events=events)
    return CareerWorkflowService(
        session,
        user_id,
        notifications=notifications,
        progress=progress,
        content_fn=_make_content_fn(),
        resume_fn=_make_resume_fn(),
        outreach_fn=_make_outreach_fn(notifications),
    )


def _make_resume_fn():
    def resume_fn(
        session: Session, user_id: uuid.UUID, outputs: dict[str, Any]
    ) -> dict[str, Any]:
        match_id = _uuid(outputs.get("job_match_id"))
        if match_id is None:
            return {"resume_version_id": None, "customized": False, "note": "no_match"}

        match = (
            session.query(JobMatch)
            .filter(JobMatch.id == match_id, JobMatch.user_id == user_id)
            .one_or_none()
        )
        if match is None:
            return {"resume_version_id": None, "customized": False, "note": "match_missing"}

        job = session.query(Job).filter(Job.id == match.job_id).one_or_none()
        job_text = " ".join(
            filter(
                None,
                [
                    job.title if job else None,
                    getattr(job, "description", None) if job else None,
                ],
            )
        )

        resume = (
            session.query(Resume)
            .filter(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc())
            .first()
        )
        if resume is None:
            return {"resume_version_id": None, "customized": False, "note": "no_resume"}

        version = (
            session.query(ResumeVersion)
            .filter(
                ResumeVersion.resume_id == resume.id,
                ResumeVersion.user_id == user_id,
            )
            .order_by(ResumeVersion.created_at.desc())
            .first()
        )
        if version is None:
            return {"resume_version_id": None, "customized": False, "note": "no_version"}

        scorer = AtsScoreService()
        emphasis: list[str] = []
        best_version = version
        best_score = scorer.score_text(version.plain_text or "", job_text)
        customized = False

        try:
            customizer = ResumeCustomizationService(session, user_id)
            for _ in range(3):
                if best_score.score >= 90:
                    break
                # Only emphasize keywords that already appear on the resume.
                resume_lower = (best_version.plain_text or "").lower()
                emphasis = [
                    kw
                    for kw in best_score.missing
                    if kw.lower() in resume_lower
                ][:12]
                try:
                    tailored = customizer.customize_for_match(
                        resume_id=resume.id,
                        job_match_id=match_id,
                        emphasis_skills=emphasis or None,
                    )
                    session.commit()
                    customized = True
                    best_version = tailored
                    best_score = scorer.score_text(tailored.plain_text or "", job_text)
                except Exception:
                    break
        except Exception:
            pass

        return {
            "resume_version_id": str(best_version.id),
            "customized": customized,
            "ats_score": best_score.score,
            "ats_matched": best_score.matched,
            "ats_missing": best_score.missing,
        }

    return resume_fn


def _make_content_fn():
    def content_fn(
        session: Session, user_id: uuid.UUID, outputs: dict[str, Any]
    ) -> dict[str, Any]:
        job_title = ""
        job_id = _uuid(outputs.get("job_id"))
        job: Job | None = None
        if job_id:
            job = session.query(Job).filter(Job.id == job_id).one_or_none()
            if job:
                job_title = job.title or ""

        structured = _structured_from_outputs(session, user_id, outputs)
        job_payload = {
            "title": job.title if job else job_title,
            "description": getattr(job, "description", None) if job else None,
        }
        try:
            llm = create_llm_provider()
            svc = ApplicationContentService(llm)
            generated = svc.generate(
                ContentPromptKind.cover_letter,
                structured_resume=structured,
                job=job_payload,
                user_id=user_id,
                job_id=job_id,
            )
            return {
                "content": generated.body,
                "cover_letter": generated.body,
                "warnings": list(generated.warnings),
            }
        except Exception as exc:  # noqa: BLE001
            body = (
                f"Hello,\n\nI'm applying for {job_title or 'this role'}. "
                "Please see my resume for relevant experience.\n\nThank you."
            )
            return {
                "content": body,
                "cover_letter": body,
                "note": f"content_fallback: {exc}",
            }

    return content_fn


def _make_outreach_fn(notifications: NotificationProvider | None):
    def outreach_fn(
        session: Session, user_id: uuid.UUID, outputs: dict[str, Any]
    ) -> dict[str, Any]:
        job_id = _uuid(outputs.get("job_id"))
        company_id = _uuid(outputs.get("company_id"))
        app_id = _uuid(outputs.get("application_id"))
        job = session.query(Job).filter(Job.id == job_id).one_or_none() if job_id else None
        job_title = job.title if job else "the role"
        company_name = ""
        if job is not None:
            from database.models.schema import Company

            company = (
                session.query(Company).filter(Company.id == job.company_id).one_or_none()
            )
            company_name = company.name if company else ""

        structured = _structured_from_outputs(session, user_id, outputs)
        person = None
        contact = None
        if company_id:
            contact = (
                session.query(Contact)
                .filter(Contact.user_id == user_id, Contact.company_id == company_id)
                .order_by(Contact.created_at.desc())
                .first()
            )
        if contact is None:
            people = outputs.get("people") if isinstance(outputs.get("people"), list) else []
            # Prefer persisted contact_id from people research snapshot.
            for row in people:
                if isinstance(row, dict) and row.get("contact_id"):
                    cid = _uuid(row.get("contact_id"))
                    if cid:
                        contact = (
                            session.query(Contact)
                            .filter(Contact.id == cid, Contact.user_id == user_id)
                            .one_or_none()
                        )
                        if contact:
                            break

        if contact:
            person = {
                "name": contact.name,
                "title": contact.title,
            }

        hook_subject = f"Quick note on {job_title}" + (
            f" at {company_name}" if company_name else ""
        )
        hook_body = (
            f"Hi{(' ' + (contact.name or '').split()[0]) if contact and contact.name else ''},\n\n"
            f"I noticed the {job_title} opening"
            f"{f' at {company_name}' if company_name else ''} and thought it was worth a short note. "
            "Happy to share a tailored resume if useful.\n\nThanks"
        )

        try:
            llm = create_llm_provider()
            svc = ApplicationContentService(llm)
            kind = ContentPromptKind.recruiter_outreach
            generated = svc.generate(
                kind,
                structured_resume=structured,
                job={
                    "title": job_title,
                    "description": getattr(job, "description", None) if job else None,
                },
                company={"name": company_name} if company_name else None,
                person=person,
                user_id=user_id,
                job_id=job_id,
                company_id=company_id,
            )
            hook_body = generated.body
            if generated.subject:
                hook_subject = generated.subject
            else:
                # Prefer a hooky subject line for open rates.
                hook_subject = f"Idea for {job_title}" + (
                    f" @ {company_name}" if company_name else ""
                )
        except Exception:
            pass

        result: dict[str, Any] = {
            "hook_subject": hook_subject,
            "hook_body": hook_body,
            "outreach": None,
            "outreach_id": None,
        }

        if contact is None:
            result["note"] = "no_contact"
            return result

        try:
            outreach = OutreachService(
                session, user_id, notifications=notifications
            ).create_draft(
                OutreachDraftInput(
                    contact_id=contact.id,
                    outreach_type=OutreachType.recruiter,
                    subject=hook_subject,
                    body=hook_body,
                    reason="career_pipeline_package",
                    application_id=app_id,
                    job_id=job_id,
                    company_id=company_id or (job.company_id if job else None),
                    request_approval=True,
                )
            )
            result["outreach"] = outreach.model_dump(mode="json")
            result["outreach_id"] = str(outreach.id)
        except Exception as exc:  # noqa: BLE001
            result["note"] = f"outreach_draft_failed: {exc}"

        return result

    return outreach_fn


def _structured_from_outputs(
    session: Session, user_id: uuid.UUID, outputs: dict[str, Any]
) -> StructuredResume:
    version_id = _uuid(outputs.get("resume_version_id"))
    if version_id:
        version = (
            session.query(ResumeVersion)
            .filter(ResumeVersion.id == version_id, ResumeVersion.user_id == user_id)
            .one_or_none()
        )
        if version is not None and version.sections:
            try:
                return StructuredResume.model_validate(version.sections)
            except Exception:
                pass
        if version is not None and version.plain_text:
            return StructuredResume(summary=version.plain_text[:500], skills=[])
    return StructuredResume()


def _uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None
