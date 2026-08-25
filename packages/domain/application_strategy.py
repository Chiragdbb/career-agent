"""ApplicationStrategyService — recommend actions to maximize interview probability.

Does not send emails or submit applications. Returns approvals required.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from packages.domain.people_models import DiscoveredPerson, RolePriority
from packages.domain.preferences import (
    ApplicationAutomationMode,
    OutreachApprovalMode,
    PreferenceSettings,
)


class StrategyActionType(StrEnum):
    customize_resume = "customize_resume"
    generate_cover_letter = "generate_cover_letter"
    research_company = "research_company"
    research_people = "research_people"
    outreach_recruiter = "outreach_recruiter"
    outreach_hiring_manager = "outreach_hiring_manager"
    request_referral = "request_referral"
    prepare_application = "prepare_application"
    await_user_approval = "await_user_approval"
    skip_low_fit = "skip_low_fit"


class ApprovalKind(StrEnum):
    outreach_send = "outreach_send"
    application_submit = "application_submit"
    resume_finalize = "resume_finalize"
    content_review = "content_review"


class StrategyAction(BaseModel):
    action: StrategyActionType
    priority: int = Field(ge=1, description="1 = highest priority")
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    required_approvals: list[ApprovalKind] = Field(default_factory=list)
    target_contact_id: UUID | None = None
    target_person_name: str | None = None


class StrategyInput(BaseModel):
    job_match_id: UUID | None = None
    job_id: UUID | None = None
    job_title: str | None = None
    company_name: str | None = None
    match_score: float | None = None
    match_notes: list[str] = Field(default_factory=list)
    company_research_available: bool = False
    company_research_summary: str | None = None
    people: list[DiscoveredPerson] = Field(default_factory=list)
    has_canonical_resume: bool = False
    preferences: PreferenceSettings = Field(default_factory=PreferenceSettings)


class ApplicationStrategy(BaseModel):
    recommended_actions: list[StrategyAction]
    overall_priority: int
    overall_confidence: float
    interview_probability_focus: bool = True
    summary: str


class ApplicationStrategyService:
    """Deterministic strategy from match + research + preferences (no side effects)."""

    HIGH_FIT = 0.72
    MEDIUM_FIT = 0.45

    def build_strategy(self, inputs: StrategyInput) -> ApplicationStrategy:
        prefs = inputs.preferences
        score = inputs.match_score if inputs.match_score is not None else 0.0
        actions: list[StrategyAction] = []

        if score < self.MEDIUM_FIT:
            actions.append(
                StrategyAction(
                    action=StrategyActionType.skip_low_fit,
                    priority=1,
                    confidence=0.85,
                    reasons=[
                        f"Match score {score:.2f} is below medium-fit threshold "
                        f"({self.MEDIUM_FIT}); prioritize higher-probability roles."
                    ],
                    required_approvals=[],
                )
            )
            return ApplicationStrategy(
                recommended_actions=actions,
                overall_priority=99,
                overall_confidence=0.85,
                summary="Low fit — skip to protect interview probability over volume.",
            )

        priority = 1
        if not inputs.company_research_available:
            actions.append(
                StrategyAction(
                    action=StrategyActionType.research_company,
                    priority=priority,
                    confidence=0.9,
                    reasons=["Company context missing; research improves targeting."],
                )
            )
            priority += 1

        if not inputs.people:
            actions.append(
                StrategyAction(
                    action=StrategyActionType.research_people,
                    priority=priority,
                    confidence=0.88,
                    reasons=["No contacts yet; recruiter/HM outreach raises interview odds."],
                )
            )
            priority += 1

        if inputs.has_canonical_resume:
            actions.append(
                StrategyAction(
                    action=StrategyActionType.customize_resume,
                    priority=priority,
                    confidence=0.8 if score >= self.HIGH_FIT else 0.7,
                    reasons=[
                        "Tailor resume emphasis to job keywords without inventing facts.",
                    ],
                    required_approvals=[ApprovalKind.resume_finalize],
                )
            )
            priority += 1
            actions.append(
                StrategyAction(
                    action=StrategyActionType.generate_cover_letter,
                    priority=priority,
                    confidence=0.75,
                    reasons=["Cover letter helps when fit is solid; content needs review."],
                    required_approvals=[ApprovalKind.content_review],
                )
            )
            priority += 1

        recruiter = _best_person(inputs.people, {RolePriority.recruiter, RolePriority.role_recruiter})
        hm = _best_person(
            inputs.people,
            {RolePriority.hiring_manager, RolePriority.engineering_manager},
        )
        referral = _best_person(inputs.people, {RolePriority.referral, RolePriority.employee})

        outreach_approvals = _outreach_approvals(prefs.outreach_approval_mode)

        if recruiter and score >= self.MEDIUM_FIT:
            actions.append(
                StrategyAction(
                    action=StrategyActionType.outreach_recruiter,
                    priority=priority,
                    confidence=min(0.95, recruiter.confidence + 0.1),
                    reasons=[
                        f"Recruiter contact '{recruiter.name}' is highest-leverage first touch.",
                        "Optimize for interview probability, not application volume.",
                    ],
                    required_approvals=outreach_approvals,
                    target_contact_id=recruiter.contact_id,
                    target_person_name=recruiter.name,
                )
            )
            priority += 1

        if hm and score >= self.HIGH_FIT:
            actions.append(
                StrategyAction(
                    action=StrategyActionType.outreach_hiring_manager,
                    priority=priority,
                    confidence=hm.confidence,
                    reasons=[
                        "High fit warrants hiring-manager message after recruiter touch.",
                    ],
                    required_approvals=outreach_approvals,
                    target_contact_id=hm.contact_id,
                    target_person_name=hm.name,
                )
            )
            priority += 1

        if referral and score >= self.HIGH_FIT:
            actions.append(
                StrategyAction(
                    action=StrategyActionType.request_referral,
                    priority=priority,
                    confidence=referral.confidence,
                    reasons=["Employee/referral path can raise interview probability."],
                    required_approvals=outreach_approvals,
                    target_contact_id=referral.contact_id,
                    target_person_name=referral.name,
                )
            )
            priority += 1

        submit_approvals = [ApprovalKind.application_submit]
        if prefs.application_automation_mode == ApplicationAutomationMode.manual:
            submit_approvals.append(ApprovalKind.content_review)

        actions.append(
            StrategyAction(
                action=StrategyActionType.prepare_application,
                priority=priority,
                confidence=0.7 if score >= self.HIGH_FIT else 0.55,
                reasons=[
                    "Prepare application packet only; never auto-submit without evidence path.",
                ],
                required_approvals=submit_approvals,
            )
        )
        priority += 1

        actions.append(
            StrategyAction(
                action=StrategyActionType.await_user_approval,
                priority=priority,
                confidence=1.0,
                reasons=["External communication and submission require explicit approval."],
                required_approvals=[ApprovalKind.outreach_send, ApprovalKind.application_submit],
            )
        )

        overall_confidence = round(
            sum(a.confidence for a in actions) / max(len(actions), 1),
            2,
        )
        overall_priority = 1 if score >= self.HIGH_FIT else (2 if score >= self.MEDIUM_FIT else 99)
        summary = (
            f"High-fit strategy for {inputs.job_title or 'role'} at "
            f"{inputs.company_name or 'company'} (score={score:.2f})."
            if score >= self.HIGH_FIT
            else f"Selective medium-fit plan (score={score:.2f}); favor quality over volume."
        )
        return ApplicationStrategy(
            recommended_actions=actions,
            overall_priority=overall_priority,
            overall_confidence=overall_confidence,
            summary=summary,
        )


def _best_person(
    people: list[DiscoveredPerson],
    roles: set[RolePriority],
) -> DiscoveredPerson | None:
    matches = [p for p in people if p.relevance in roles]
    if not matches:
        return None
    return max(matches, key=lambda p: p.confidence)


def _outreach_approvals(mode: OutreachApprovalMode) -> list[ApprovalKind]:
    if mode == OutreachApprovalMode.auto_when_rules:
        # Still require approval unless explicit automation rules exist (not modeled yet).
        return [ApprovalKind.outreach_send]
    return [ApprovalKind.outreach_send]
