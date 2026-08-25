"""User job-search and automation preferences (tenant-scoped JSONB settings)."""

from __future__ import annotations

import enum
import uuid

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from database.models.enums import UserPreferenceStatus
from database.models.schema import UserPreference
from packages.domain.exceptions import DomainError


class WorkArrangement(str, enum.Enum):
    remote = "remote"
    hybrid = "hybrid"
    on_site = "on_site"


class SeniorityLevel(str, enum.Enum):
    intern = "intern"
    entry = "entry"
    mid = "mid"
    senior = "senior"
    staff = "staff"
    principal = "principal"
    executive = "executive"


class CompanySize(str, enum.Enum):
    startup = "startup"  # 1-50
    small = "small"  # 51-200
    medium = "medium"  # 201-1000
    large = "large"  # 1001-5000
    enterprise = "enterprise"  # 5000+


class EmploymentType(str, enum.Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"
    temporary = "temporary"


class JobFreshness(str, enum.Enum):
    last_24h = "last_24h"
    last_3d = "last_3d"
    last_7d = "last_7d"
    last_14d = "last_14d"
    last_30d = "last_30d"
    any = "any"


class ApplicationAutomationMode(str, enum.Enum):
    manual = "manual"
    assisted = "assisted"
    auto_with_approval = "auto_with_approval"


class OutreachApprovalMode(str, enum.Enum):
    always_approve = "always_approve"
    approve_each = "approve_each"
    auto_when_rules = "auto_when_rules"


class PreferenceSettings(BaseModel):
    """Structured preferences stored in user_preferences.settings JSONB."""

    target_roles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_arrangements: list[WorkArrangement] = Field(default_factory=list)
    minimum_salary: int | None = None
    seniority: list[SeniorityLevel] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    company_sizes: list[CompanySize] = Field(default_factory=list)
    employment_types: list[EmploymentType] = Field(default_factory=list)
    job_freshness: JobFreshness = JobFreshness.last_7d
    application_automation_mode: ApplicationAutomationMode = (
        ApplicationAutomationMode.manual
    )
    outreach_approval_mode: OutreachApprovalMode = OutreachApprovalMode.approve_each
    daily_application_limit: int = Field(default=5, ge=0, le=100)
    daily_outreach_limit: int = Field(default=10, ge=0, le=100)

    @field_validator("target_roles", "locations", "industries", mode="before")
    @classmethod
    def normalize_string_lists(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("must be a list")
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("list items must be strings")
            stripped = item.strip()
            if stripped:
                cleaned.append(stripped)
        return cleaned

    @field_validator("minimum_salary")
    @classmethod
    def validate_minimum_salary(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("minimum_salary must be non-negative")
        return value


class PreferencesService:
    """Manage job-search preferences for one tenant."""

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def get_or_create(self) -> UserPreference:
        row = (
            self._session.query(UserPreference)
            .filter(UserPreference.user_id == self._user_id)
            .one_or_none()
        )
        if row is None:
            row = UserPreference(
                id=uuid.uuid4(),
                user_id=self._user_id,
                status=UserPreferenceStatus.active,
                settings=PreferenceSettings().model_dump(mode="json"),
            )
            self._session.add(row)
            self._session.commit()
            self._session.refresh(row)
        return row

    def get_settings(self) -> PreferenceSettings:
        row = self.get_or_create()
        raw = row.settings or {}
        try:
            return PreferenceSettings.model_validate(raw)
        except Exception as exc:
            raise DomainError("Stored preferences are invalid") from exc

    def update(self, settings: PreferenceSettings) -> UserPreference:
        row = self.get_or_create()
        row.settings = settings.model_dump(mode="json")
        self._session.commit()
        self._session.refresh(row)
        return row
