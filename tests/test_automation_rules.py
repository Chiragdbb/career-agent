"""AutomationRuleEngine tests — safe actions only, dry-run, limits, audit."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from packages.domain.automation_rules import (
    AutomationActionType,
    AutomationCondition,
    AutomationConditionField,
    AutomationContext,
    AutomationOperator,
    AutomationRule,
    AutomationRuleEngine,
)


def test_rule_matches_and_dry_run() -> None:
    session = MagicMock()
    engine = AutomationRuleEngine(session, uuid.uuid4())
    rule = AutomationRule(
        name="shortlist high fit",
        conditions=[
            AutomationCondition(
                field=AutomationConditionField.match_score,
                operator=AutomationOperator.gte,
                value=0.8,
            )
        ],
        actions=[AutomationActionType.shortlist_job, AutomationActionType.notify_user],
        dry_run=True,
        require_approval=False,
    )
    engine.list_rules = lambda: [rule]  # type: ignore[method-assign]
    decisions = engine.evaluate(AutomationContext(match_score=0.9, entity_type="job_match"))
    assert len(decisions) == 1
    assert decisions[0].matched is True
    assert decisions[0].dry_run is True
    assert decisions[0].executed[0].startswith("dry_run:")


def test_submit_always_requires_approval() -> None:
    session = MagicMock()
    engine = AutomationRuleEngine(session, uuid.uuid4())
    rule = AutomationRule(
        name="auto submit",
        conditions=[],
        actions=[AutomationActionType.submit_application],
        require_approval=False,
        dry_run=False,
    )
    engine.list_rules = lambda: [rule]  # type: ignore[method-assign]
    decisions = engine.evaluate(AutomationContext(match_score=1.0))
    assert decisions[0].require_approval is True


def test_daily_limit_blocks() -> None:
    session = MagicMock()
    engine = AutomationRuleEngine(session, uuid.uuid4())
    rule = AutomationRule(
        name="prep",
        conditions=[],
        actions=[AutomationActionType.prepare_application],
        daily_limit=2,
        dry_run=False,
    )
    engine.list_rules = lambda: [rule]  # type: ignore[method-assign]
    decisions = engine.evaluate(AutomationContext(daily_applications=2))
    assert decisions[0].blocked_reason == "daily_application_limit"


def test_rejects_empty_actions() -> None:
    with pytest.raises(Exception):
        AutomationRule(name="bad", actions=[])
