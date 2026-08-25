"""STEP 17 — ApplicationStrategyService."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from packages.domain.application_strategy import (
    ApplicationStrategyService,
    ApprovalKind,
    StrategyActionType,
    StrategyInput,
)
from packages.domain.people_models import DiscoveredPerson, RolePriority
from packages.domain.preferences import PreferenceSettings


def _person(name: str, role: RolePriority, confidence: float = 0.8) -> DiscoveredPerson:
    return DiscoveredPerson(
        name=name,
        title=role.value,
        company="Acme",
        source="people_provider",
        relevance=role,
        confidence=confidence,
        provider="mock-people",
        discovered_at=datetime.now(timezone.utc),
        contact_id=uuid.uuid4(),
    )


def test_low_fit_skips_for_interview_probability() -> None:
    strategy = ApplicationStrategyService().build_strategy(
        StrategyInput(match_score=0.2, job_title="Intern", company_name="Acme")
    )
    assert strategy.recommended_actions[0].action == StrategyActionType.skip_low_fit
    assert strategy.overall_priority == 99


def test_high_fit_recommends_recruiter_then_approvals() -> None:
    strategy = ApplicationStrategyService().build_strategy(
        StrategyInput(
            match_score=0.9,
            job_title="Senior Engineer",
            company_name="Acme",
            company_research_available=True,
            has_canonical_resume=True,
            people=[
                _person("Riley", RolePriority.role_recruiter, 0.9),
                _person("Morgan", RolePriority.engineering_manager, 0.85),
            ],
            preferences=PreferenceSettings(),
        )
    )
    actions = [a.action for a in strategy.recommended_actions]
    assert StrategyActionType.customize_resume in actions
    assert StrategyActionType.outreach_recruiter in actions
    assert StrategyActionType.prepare_application in actions
    assert StrategyActionType.await_user_approval in actions
    recruiter = next(
        a for a in strategy.recommended_actions if a.action == StrategyActionType.outreach_recruiter
    )
    assert ApprovalKind.outreach_send in recruiter.required_approvals
    assert strategy.interview_probability_focus is True


def test_missing_research_prioritized() -> None:
    strategy = ApplicationStrategyService().build_strategy(
        StrategyInput(match_score=0.6, company_research_available=False, people=[])
    )
    assert strategy.recommended_actions[0].action == StrategyActionType.research_company
    assert strategy.recommended_actions[1].action == StrategyActionType.research_people
