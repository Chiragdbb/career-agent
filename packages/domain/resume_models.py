"""Structured resume models — canonical candidate facts extracted from uploads.

Never invent experience, skills, dates, employers, achievements, or metrics.
Only fields present in source text should be populated.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


PARSER_VERSION = "heuristic-v1"


class ContactInfo(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None


class ExperienceEntry(BaseModel):
    company: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    bullets: list[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    technologies: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    details: list[str] = Field(default_factory=list)


class CertificationEntry(BaseModel):
    name: str | None = None
    issuer: str | None = None
    date: str | None = None
    credential_id: str | None = None
    url: str | None = None


class StructuredResume(BaseModel):
    """Canonical structured representation of a resume version."""

    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str | None = None
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    parser_version: str = PARSER_VERSION


class ResumeDocumentInfo(BaseModel):
    id: UUID
    filename: str | None = None
    mime_type: str | None = None
    storage_path: str | None = None
    checksum: str | None = None
    status: str


class ResumeVersionInfo(BaseModel):
    id: UUID
    status: str
    content_hash: str | None = None
    plain_text: str | None = None
    structured: StructuredResume | None = None
    parser_version: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    document: ResumeDocumentInfo | None = None


class ResumeSummary(BaseModel):
    id: UUID
    name: str
    status: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    latest_version_id: UUID | None = None
    parser_version: str | None = None


class ResumeDetail(BaseModel):
    id: UUID
    name: str
    status: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    latest_version: ResumeVersionInfo | None = None
    signed_url: str | None = None
