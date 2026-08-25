"""Models for people / contact discovery (never invent emails)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class RolePriority(StrEnum):
    """Discovery priority — lower rank value is higher priority."""

    recruiter = "recruiter"
    role_recruiter = "role_recruiter"
    hiring_manager = "hiring_manager"
    engineering_manager = "engineering_manager"
    employee = "employee"
    referral = "referral"


ROLE_PRIORITY_ORDER: tuple[RolePriority, ...] = (
    RolePriority.recruiter,
    RolePriority.role_recruiter,
    RolePriority.hiring_manager,
    RolePriority.engineering_manager,
    RolePriority.employee,
    RolePriority.referral,
)

# Title keywords used to classify and search (case-insensitive substring match).
ROLE_TITLE_KEYWORDS: dict[RolePriority, tuple[str, ...]] = {
    RolePriority.recruiter: (
        "recruiter",
        "talent acquisition",
        "ta partner",
        "recruiting coordinator",
    ),
    RolePriority.role_recruiter: (
        "technical recruiter",
        "engineering recruiter",
        "sourcer",
        "talent sourcer",
    ),
    RolePriority.hiring_manager: (
        "hiring manager",
        "head of",
        "director of",
        "vp of",
        "vice president",
    ),
    RolePriority.engineering_manager: (
        "engineering manager",
        "eng manager",
        "software engineering manager",
        "manager, engineering",
        "em ",
    ),
    RolePriority.employee: (
        "engineer",
        "developer",
        "software",
        "staff",
        "senior",
    ),
    RolePriority.referral: (
        "referral",
        "alumni",
        "former",
    ),
}


class DiscoveredPerson(BaseModel):
    """Normalized person hit ready for persistence / strategy use."""

    name: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    source: str
    relevance: RolePriority
    confidence: float = Field(ge=0.0, le=1.0)
    provider: str
    discovered_at: datetime
    linkedin_url: str | None = None
    email: str | None = None
    email_verified: bool = False
    email_verification_status: str | None = None
    people_id: UUID | None = None
    contact_id: UUID | None = None


class PeopleResearchResult(BaseModel):
    company_id: UUID
    company_name: str
    job_id: UUID | None = None
    job_title: str | None = None
    people: list[DiscoveredPerson] = Field(default_factory=list)
    searched_roles: list[RolePriority] = Field(default_factory=list)
