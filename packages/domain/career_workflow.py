"""CareerWorkflowService — orchestrate per-job career pipeline.

match → research → people → strategy → resume → content → approval pause →
prepare application → (submit if permitted) → outreach draft → follow-up schedule → notify

Resumable, idempotent (via workflow_tasks), observable (workflow_runs + events).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models.enums import (
    ApplicationStatus,
    JobMatchStatus,
    WorkflowRunStatus,
    WorkflowTaskStatus,
)
from database.models.schema import (
    Application,
    Job,
    JobMatch,
    Resume,
    ResumeVersion,
    WorkflowRun,
    WorkflowTask,
)
from packages.domain.application_engine import ApplicationEngine, EngineState
from packages.domain.application_strategy import (
    ApplicationStrategyService,
    StrategyInput,
)
from packages.domain.exceptions import DomainError, NotFoundError
from packages.domain.human_tasks import (
    HumanTaskCreate,
    HumanTaskService,
    HumanTaskType,
)
from packages.domain.preferences import (
    ApplicationAutomationMode,
    PreferencesService,
)
from packages.providers.notification import (
    NotificationChannel,
    NotificationProvider,
    NotificationSendRequest,
)


class CareerWorkflowStep(StrEnum):
    match = "match"
    research = "research"
    people = "people"
    strategy = "strategy"
    resume = "resume"
    content = "content"
    approval_pause = "approval_pause"
    prepare_application = "prepare_application"
    submit_application = "submit_application"
    outreach_draft = "outreach_draft"
    follow_up_schedule = "follow_up_schedule"
    notify = "notify"


STEP_ORDER: list[CareerWorkflowStep] = list(CareerWorkflowStep)


class CareerWorkflowStart(BaseModel):
    job_match_id: uuid.UUID
    permit_submit: bool = False
    resume_version_id: uuid.UUID | None = None
    force: bool = False


class CareerWorkflowResult(BaseModel):
    workflow_run_id: uuid.UUID
    status: str
    paused: bool = False
    human_task_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    completed_steps: list[str] = Field(default_factory=list)
    current_step: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


# Optional injectable step runners for tests / workers.
ResearchFn = Callable[[Session, uuid.UUID, uuid.UUID], dict[str, Any]]
PeopleFn = Callable[[Session, uuid.UUID, uuid.UUID], dict[str, Any]]
ResumeFn = Callable[[Session, uuid.UUID, dict[str, Any]], dict[str, Any]]
ContentFn = Callable[[Session, uuid.UUID, dict[str, Any]], dict[str, Any]]
OutreachFn = Callable[[Session, uuid.UUID, dict[str, Any]], dict[str, Any]]


class CareerWorkflowService:
    """Tenant-scoped orchestration for one job match."""

    WORKFLOW_TYPE = "career_job_pipeline"

    def __init__(
        self,
        session: Session,
        user_id: uuid.UUID,
        *,
        human_tasks: HumanTaskService | None = None,
        notifications: NotificationProvider | None = None,
        strategy_service: ApplicationStrategyService | None = None,
        research_fn: ResearchFn | None = None,
        people_fn: PeopleFn | None = None,
        resume_fn: ResumeFn | None = None,
        content_fn: ContentFn | None = None,
        outreach_fn: OutreachFn | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._notifications = notifications
        self._human_tasks = human_tasks or HumanTaskService(
            session, user_id, notifications=notifications
        )
        self._strategy = strategy_service or ApplicationStrategyService()
        self._research_fn = research_fn
        self._people_fn = people_fn
        self._resume_fn = resume_fn
        self._content_fn = content_fn
        self._outreach_fn = outreach_fn

    def start_or_resume(self, payload: CareerWorkflowStart) -> CareerWorkflowResult:
        match = self._get_match(payload.job_match_id)
        run = self._find_or_create_run(match, payload)
        meta = dict(run.metadata_json or {})

        if meta.get("paused") and not payload.force:
            return CareerWorkflowResult(
                workflow_run_id=run.id,
                status=run.status.value,
                paused=True,
                human_task_id=_uuid_or_none(meta.get("pause_human_task_id")),
                application_id=_uuid_or_none(meta.get("application_id")),
                completed_steps=list(meta.get("completed_steps") or []),
                current_step=meta.get("current_step"),
                outputs=dict(meta.get("outputs") or {}),
                errors=list(meta.get("errors") or []),
            )

        run.status = WorkflowRunStatus.running
        meta["paused"] = False
        meta["permit_submit"] = payload.permit_submit
        if payload.resume_version_id:
            meta["resume_version_id"] = str(payload.resume_version_id)
        run.metadata_json = meta
        self._session.commit()

        completed = list(meta.get("completed_steps") or [])
        outputs = dict(meta.get("outputs") or {})
        errors: list[str] = list(meta.get("errors") or [])

        try:
            for step in STEP_ORDER:
                if step.value in completed:
                    continue
                meta["current_step"] = step.value
                run.metadata_json = meta
                self._session.commit()

                if self._task_already_completed(run.id, step.value):
                    completed.append(step.value)
                    continue

                task = self._begin_task(run.id, step.value, input_payload={"match_id": str(match.id)})
                try:
                    step_out = self._run_step(
                        step, match, meta, outputs, payload, run_id=run.id
                    )
                except _PauseWorkflow as pause:
                    self._complete_task(task, output=pause.output, status=WorkflowTaskStatus.completed)
                    completed.append(step.value)
                    meta["completed_steps"] = completed
                    meta["outputs"] = {**outputs, **(pause.output or {})}
                    meta["paused"] = True
                    meta["pause_human_task_id"] = str(pause.human_task_id)
                    meta["current_step"] = step.value
                    run.metadata_json = meta
                    run.status = WorkflowRunStatus.running
                    self._session.commit()
                    return CareerWorkflowResult(
                        workflow_run_id=run.id,
                        status=run.status.value,
                        paused=True,
                        human_task_id=pause.human_task_id,
                        application_id=_uuid_or_none(meta.get("application_id")),
                        completed_steps=completed,
                        current_step=step.value,
                        outputs=meta["outputs"],
                        errors=errors,
                    )
                except Exception as exc:  # noqa: BLE001
                    self._fail_task(task, error=str(exc))
                    errors.append(f"{step.value}: {exc}")
                    meta["errors"] = errors
                    meta["completed_steps"] = completed
                    meta["outputs"] = outputs
                    run.metadata_json = meta
                    run.status = WorkflowRunStatus.failed
                    run.error = str(exc)
                    self._session.commit()
                    return CareerWorkflowResult(
                        workflow_run_id=run.id,
                        status=run.status.value,
                        paused=False,
                        application_id=_uuid_or_none(meta.get("application_id")),
                        completed_steps=completed,
                        current_step=step.value,
                        outputs=outputs,
                        errors=errors,
                    )

                self._complete_task(task, output=step_out)
                outputs.update(step_out or {})
                completed.append(step.value)
                meta["completed_steps"] = completed
                meta["outputs"] = outputs
                run.metadata_json = meta
                self._session.commit()

            run.status = WorkflowRunStatus.completed
            meta["current_step"] = None
            meta["finished_at"] = datetime.now(timezone.utc).isoformat()
            run.metadata_json = meta
            self._session.commit()
            return CareerWorkflowResult(
                workflow_run_id=run.id,
                status=run.status.value,
                paused=False,
                application_id=_uuid_or_none(meta.get("application_id")),
                completed_steps=completed,
                current_step=None,
                outputs=outputs,
                errors=errors,
            )
        except Exception as exc:  # noqa: BLE001
            run.status = WorkflowRunStatus.failed
            run.error = str(exc)
            self._session.commit()
            raise

    def _run_step(
        self,
        step: CareerWorkflowStep,
        match: JobMatch,
        meta: dict[str, Any],
        outputs: dict[str, Any],
        payload: CareerWorkflowStart,
        *,
        run_id: uuid.UUID,
    ) -> dict[str, Any]:
        job = self._session.query(Job).filter(Job.id == match.job_id).one()
        prefs = PreferencesService(self._session, self._user_id).get_settings()
        meta["workflow_run_id"] = str(run_id)

        if step == CareerWorkflowStep.match:
            return {
                "job_match_id": str(match.id),
                "job_id": str(job.id),
                "company_id": str(job.company_id),
                "match_score": float(match.score) if match.score is not None else None,
                "match_status": match.status.value,
            }

        if step == CareerWorkflowStep.research:
            if self._research_fn:
                return self._research_fn(self._session, self._user_id, job.id)
            return {
                "research": "stub",
                "company_id": str(job.company_id),
                "note": "Inject research_fn or run research worker for full research",
            }

        if step == CareerWorkflowStep.people:
            if self._people_fn:
                return self._people_fn(self._session, self._user_id, job.company_id)
            return {"people": [], "note": "Inject people_fn or run contacts worker"}

        if step == CareerWorkflowStep.strategy:
            strategy = self._strategy.build_strategy(
                StrategyInput(
                    job_match_id=match.id,
                    job_id=job.id,
                    job_title=job.title,
                    match_score=float(match.score) if match.score is not None else 0.0,
                    company_research_available=bool(outputs.get("research")),
                    preferences=prefs,
                )
            )
            return {
                "strategy_summary": strategy.summary,
                "strategy_actions": [a.model_dump(mode="json") for a in strategy.recommended_actions],
                "overall_confidence": strategy.overall_confidence,
            }

        if step == CareerWorkflowStep.resume:
            if self._resume_fn:
                return self._resume_fn(self._session, self._user_id, outputs)
            version_id = meta.get("resume_version_id")
            if not version_id:
                version_id = self._default_resume_version_id()
            if not version_id:
                raise DomainError("No resume_version available for workflow")
            meta["resume_version_id"] = str(version_id)
            return {"resume_version_id": str(version_id), "customized": False}

        if step == CareerWorkflowStep.content:
            if self._content_fn:
                return self._content_fn(self._session, self._user_id, outputs)
            return {"content": "stub", "cover_letter": None}

        if step == CareerWorkflowStep.approval_pause:
            # Always pause for application approval unless automation is auto_with_approval
            # AND permit_submit was already granted for this run.
            needs_approval = True
            if (
                prefs.application_automation_mode == ApplicationAutomationMode.auto_with_approval
                and payload.permit_submit
            ):
                needs_approval = False
            if not needs_approval:
                return {"approval": "skipped_auto_with_permit"}

            app_id = self._ensure_application(match, meta)
            engine = ApplicationEngine(self._session, self._user_id)
            state = engine.get_state(app_id)
            if state == EngineState.PREPARED:
                engine.transition(app_id, EngineState.AWAITING_APPROVAL, reason="workflow_approval")
            task = self._human_tasks.create(
                HumanTaskCreate(
                    task_type=HumanTaskType.approval_required_application,
                    title=f"Approve application for {job.title}",
                    details={"job_id": str(job.id), "job_match_id": str(match.id)},
                    application_id=app_id,
                    workflow_run_id=run_id,
                    blocking_entity_type="application",
                    blocking_entity_id=app_id,
                )
            )
            raise _PauseWorkflow(
                human_task_id=task.id,
                output={"application_id": str(app_id), "approval": "paused", "human_task_id": str(task.id)},
            )

        if step == CareerWorkflowStep.prepare_application:
            app_id = self._ensure_application(match, meta)
            engine = ApplicationEngine(self._session, self._user_id)
            state = engine.get_state(app_id)
            if state == EngineState.AWAITING_APPROVAL:
                engine.transition(app_id, EngineState.IN_PROGRESS, reason="approved")
            elif state == EngineState.PREPARED:
                engine.transition(app_id, EngineState.AWAITING_APPROVAL, reason="prepare")
                engine.transition(app_id, EngineState.IN_PROGRESS, reason="auto_continue")
            elif state == EngineState.REQUIRES_HUMAN:
                engine.transition(app_id, EngineState.IN_PROGRESS, reason="human_resolved")
            meta["application_id"] = str(app_id)
            return {"application_id": str(app_id), "engine_state": engine.get_state(app_id).value}

        if step == CareerWorkflowStep.submit_application:
            app_id = _uuid_or_none(meta.get("application_id")) or self._ensure_application(match, meta)
            if not payload.permit_submit:
                return {
                    "submitted": False,
                    "reason": "submit not permitted; skipped (no SUBMITTED without evidence)",
                }
            # Never mark SUBMITTED without evidence — leave IN_PROGRESS for ATS worker.
            return {
                "submitted": False,
                "reason": "ATS submit delegated to applications worker; evidence required",
                "application_id": str(app_id),
            }

        if step == CareerWorkflowStep.outreach_draft:
            if self._outreach_fn:
                return self._outreach_fn(self._session, self._user_id, outputs)
            return {
                "outreach": "stub_draft",
                "note": "Inject outreach_fn to create OutreachService drafts",
            }

        if step == CareerWorkflowStep.follow_up_schedule:
            follow_at = datetime.now(timezone.utc).isoformat()
            return {
                "follow_up": {
                    "scheduled": True,
                    "suggested_at": follow_at,
                    "type": "follow_up",
                    "note": "Schedule stored in workflow outputs; notifications worker can pick up",
                }
            }

        if step == CareerWorkflowStep.notify:
            if self._notifications is not None:
                self._notifications.send(
                    NotificationSendRequest(
                        user_id=self._user_id,
                        channel=NotificationChannel.in_app,
                        title="Career workflow update",
                        body=f"Pipeline finished for job match {match.id}",
                        payload={
                            "job_match_id": str(match.id),
                            "application_id": meta.get("application_id"),
                        },
                    )
                )
            return {"notified": True}

        raise DomainError(f"Unknown step {step}")

    def _ensure_application(self, match: JobMatch, meta: dict[str, Any]) -> uuid.UUID:
        existing_id = _uuid_or_none(meta.get("application_id"))
        if existing_id:
            return existing_id
        existing = (
            self._session.query(Application)
            .filter(
                Application.user_id == self._user_id,
                Application.job_id == match.job_id,
            )
            .one_or_none()
        )
        if existing:
            meta["application_id"] = str(existing.id)
            return existing.id

        version_id = _uuid_or_none(meta.get("resume_version_id"))
        if not version_id:
            version_id = self._default_resume_version_id()
        if not version_id:
            raise DomainError("Cannot create application without resume_version")

        app = Application(
            id=uuid.uuid4(),
            user_id=self._user_id,
            job_id=match.job_id,
            resume_version_id=version_id,
            status=ApplicationStatus.draft,
            submission_evidence={"engine_status": EngineState.PREPARED.value},
        )
        self._session.add(app)
        self._session.flush()
        meta["application_id"] = str(app.id)
        match.status = JobMatchStatus.saved
        return app.id

    def _default_resume_version_id(self) -> uuid.UUID | None:
        version = (
            self._session.query(ResumeVersion)
            .join(Resume, Resume.id == ResumeVersion.resume_id)
            .filter(Resume.user_id == self._user_id)
            .order_by(ResumeVersion.created_at.desc())
            .first()
        )
        return version.id if version else None

    def _get_match(self, job_match_id: uuid.UUID) -> JobMatch:
        row = (
            self._session.query(JobMatch)
            .filter(JobMatch.id == job_match_id, JobMatch.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            raise NotFoundError("Job match not found")
        return row

    def _find_or_create_run(
        self, match: JobMatch, payload: CareerWorkflowStart
    ) -> WorkflowRun:
        existing = (
            self._session.query(WorkflowRun)
            .filter(
                WorkflowRun.user_id == self._user_id,
                WorkflowRun.workflow_type == self.WORKFLOW_TYPE,
            )
            .order_by(WorkflowRun.created_at.desc())
            .all()
        )
        for run in existing:
            meta = run.metadata_json if isinstance(run.metadata_json, dict) else {}
            if meta.get("job_match_id") == str(match.id) and run.status in (
                WorkflowRunStatus.queued,
                WorkflowRunStatus.running,
            ):
                meta["workflow_run_id"] = str(run.id)
                run.metadata_json = meta
                return run

        run = WorkflowRun(
            id=uuid.uuid4(),
            user_id=self._user_id,
            status=WorkflowRunStatus.queued,
            workflow_type=self.WORKFLOW_TYPE,
            metadata_json={
                "job_match_id": str(match.id),
                "job_id": str(match.job_id),
                "completed_steps": [],
                "outputs": {},
                "errors": [],
                "permit_submit": payload.permit_submit,
            },
        )
        run.metadata_json["workflow_run_id"] = str(run.id)
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return run

    def _current_run_id(self, meta: dict[str, Any]) -> uuid.UUID | None:
        return _uuid_or_none(meta.get("workflow_run_id"))

    def _task_already_completed(self, run_id: uuid.UUID, task_type: str) -> bool:
        row = (
            self._session.query(WorkflowTask)
            .filter(
                WorkflowTask.workflow_run_id == run_id,
                WorkflowTask.user_id == self._user_id,
                WorkflowTask.task_type == task_type,
                WorkflowTask.status == WorkflowTaskStatus.completed,
            )
            .first()
        )
        return row is not None

    def _begin_task(
        self, run_id: uuid.UUID, task_type: str, *, input_payload: dict[str, Any]
    ) -> WorkflowTask:
        task = WorkflowTask(
            id=uuid.uuid4(),
            user_id=self._user_id,
            workflow_run_id=run_id,
            status=WorkflowTaskStatus.running,
            task_type=task_type,
            input_payload=input_payload,
            attempt=1,
        )
        self._session.add(task)
        self._session.flush()
        return task

    def _complete_task(
        self,
        task: WorkflowTask,
        *,
        output: dict[str, Any] | None,
        status: WorkflowTaskStatus = WorkflowTaskStatus.completed,
    ) -> None:
        task.status = status
        task.output_payload = output or {}

    def _fail_task(self, task: WorkflowTask, *, error: str) -> None:
        task.status = WorkflowTaskStatus.failed
        task.error = error


class _PauseWorkflow(Exception):
    def __init__(self, *, human_task_id: uuid.UUID, output: dict[str, Any]) -> None:
        self.human_task_id = human_task_id
        self.output = output
        super().__init__("workflow_paused_for_human")


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None
