"""AutomationRuleEngine — predefined safe conditions/actions only (no code exec)."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from database.models.schema import AuditLog
from packages.domain.exceptions import DomainError
from packages.domain.preferences import PreferencesService


class AutomationActionType(str, enum.Enum):
    shortlist_job = "shortlist_job"
    generate_resume = "generate_resume"
    prepare_application = "prepare_application"
    submit_application = "submit_application"
    draft_outreach = "draft_outreach"
    send_outreach = "send_outreach"
    schedule_follow_up = "schedule_follow_up"
    notify_user = "notify_user"


class AutomationConditionField(str, enum.Enum):
    match_score = "match_score"
    job_status = "job_status"
    application_status = "application_status"
    has_verified_email = "has_verified_email"
    daily_applications = "daily_applications"
    daily_outreach = "daily_outreach"


class AutomationOperator(str, enum.Enum):
    gte = "gte"
    lte = "lte"
    eq = "eq"
    neq = "neq"
    in_list = "in"


class AutomationCondition(BaseModel):
    field: AutomationConditionField
    operator: AutomationOperator
    value: Any


class AutomationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    enabled: bool = True
    conditions: list[AutomationCondition] = Field(default_factory=list)
    actions: list[AutomationActionType] = Field(default_factory=list)
    require_approval: bool = True
    daily_limit: int = Field(default=10, ge=0, le=100)
    dry_run: bool = False

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, value: list[AutomationActionType]) -> list[AutomationActionType]:
        if not value:
            raise ValueError("at least one action required")
        for action in value:
            if action not in AutomationActionType:
                raise ValueError(f"unsupported action: {action}")
        return value


class AutomationContext(BaseModel):
    """Facts evaluated against rule conditions (never raw scraped instructions)."""

    match_score: float | None = None
    job_status: str | None = None
    application_status: str | None = None
    has_verified_email: bool = False
    daily_applications: int = 0
    daily_outreach: int = 0
    entity_type: str | None = None
    entity_id: str | None = None


@dataclass
class AutomationDecision:
    rule_id: str
    rule_name: str
    matched: bool
    actions: list[AutomationActionType] = field(default_factory=list)
    require_approval: bool = True
    dry_run: bool = False
    blocked_reason: str | None = None
    executed: list[str] = field(default_factory=list)


class AutomationRuleEngine:
    """Evaluate preference-stored rules against a context; audit outcomes."""

    SAFE_ACTIONS = frozenset(AutomationActionType)

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def list_rules(self) -> list[AutomationRule]:
        prefs_row = PreferencesService(self._session, self._user_id).get_or_create()
        payload = prefs_row.settings if isinstance(prefs_row.settings, dict) else {}
        rules_raw = payload.get("automation_rules") or []
        rules: list[AutomationRule] = []
        for item in rules_raw:
            if isinstance(item, dict):
                try:
                    rules.append(AutomationRule.model_validate(item))
                except Exception:
                    continue
        return rules

    def save_rules(self, rules: list[AutomationRule]) -> list[AutomationRule]:
        prefs = PreferencesService(self._session, self._user_id)
        row = prefs.get_or_create()
        payload = dict(row.settings) if isinstance(row.settings, dict) else {}
        payload["automation_rules"] = [r.model_dump(mode="json") for r in rules]
        row.settings = payload
        self._session.commit()
        self._audit("automation_rules_saved", {"count": len(rules)})
        return rules

    def evaluate(self, context: AutomationContext) -> list[AutomationDecision]:
        decisions: list[AutomationDecision] = []
        for rule in self.list_rules():
            if not rule.enabled:
                continue
            matched = all(self._match_condition(c, context) for c in rule.conditions)
            if not matched:
                decisions.append(
                    AutomationDecision(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        matched=False,
                    )
                )
                continue
            blocked = None
            if context.daily_applications >= rule.daily_limit and (
                AutomationActionType.prepare_application in rule.actions
                or AutomationActionType.submit_application in rule.actions
            ):
                blocked = "daily_application_limit"
            if context.daily_outreach >= rule.daily_limit and (
                AutomationActionType.send_outreach in rule.actions
            ):
                blocked = "daily_outreach_limit"
            # Hard safety: submit/send always require approval unless rule says otherwise
            # AND action is not submit without evidence (engine never auto-submits evidence).
            require_approval = rule.require_approval
            if AutomationActionType.submit_application in rule.actions:
                require_approval = True
            if AutomationActionType.send_outreach in rule.actions and rule.require_approval:
                require_approval = True

            decision = AutomationDecision(
                rule_id=rule.id,
                rule_name=rule.name,
                matched=True,
                actions=list(rule.actions),
                require_approval=require_approval,
                dry_run=rule.dry_run,
                blocked_reason=blocked,
            )
            if rule.dry_run:
                decision.executed = [f"dry_run:{a.value}" for a in rule.actions]
            elif blocked:
                decision.executed = []
            else:
                decision.executed = [
                    f"queued:{a.value}" if not require_approval else f"needs_approval:{a.value}"
                    for a in rule.actions
                ]
            self._audit(
                "automation_rule_evaluated",
                {
                    "rule_id": rule.id,
                    "matched": True,
                    "actions": [a.value for a in rule.actions],
                    "dry_run": rule.dry_run,
                    "blocked_reason": blocked,
                    "entity_type": context.entity_type,
                    "entity_id": context.entity_id,
                },
            )
            decisions.append(decision)
        return decisions

    def _match_condition(self, condition: AutomationCondition, ctx: AutomationContext) -> bool:
        actual = getattr(ctx, condition.field.value, None)
        expected = condition.value
        op = condition.operator
        if op == AutomationOperator.eq:
            return actual == expected
        if op == AutomationOperator.neq:
            return actual != expected
        if op == AutomationOperator.gte:
            return actual is not None and float(actual) >= float(expected)
        if op == AutomationOperator.lte:
            return actual is not None and float(actual) <= float(expected)
        if op == AutomationOperator.in_list:
            if not isinstance(expected, (list, tuple, set)):
                raise DomainError("in operator requires a list value")
            return actual in expected
        raise DomainError(f"unsupported operator: {op}")

    def _audit(self, action: str, payload: dict[str, Any]) -> None:
        self._session.add(
            AuditLog(
                id=uuid.uuid4(),
                user_id=self._user_id,
                actor_type="system",
                action=action,
                entity_type="automation_rule",
                entity_id=None,
                metadata_json={
                    **payload,
                    "at": datetime.now(timezone.utc).isoformat(),
                },
            )
        )
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
