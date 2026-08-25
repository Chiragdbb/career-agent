"""API schemas for resume upload and retrieval."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ContactInfoResponse(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None


class ExperienceEntryResponse(BaseModel):
    company: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    bullets: list[str] = Field(default_factory=list)


class ProjectEntryResponse(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    technologies: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)


class EducationEntryResponse(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    details: list[str] = Field(default_factory=list)


class CertificationEntryResponse(BaseModel):
    name: str | None = None
    issuer: str | None = None
    date: str | None = None
    credential_id: str | None = None
    url: str | None = None


class StructuredResumeResponse(BaseModel):
    contact: ContactInfoResponse = Field(default_factory=ContactInfoResponse)
    summary: str | None = None
    experience: list[ExperienceEntryResponse] = Field(default_factory=list)
    projects: list[ProjectEntryResponse] = Field(default_factory=list)
    education: list[EducationEntryResponse] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[CertificationEntryResponse] = Field(default_factory=list)
    parser_version: str


class ResumeDocumentResponse(BaseModel):
    id: UUID
    filename: str | None = None
    mime_type: str | None = None
    storage_path: str | None = None
    checksum: str | None = None
    status: str


class ResumeVersionResponse(BaseModel):
    id: UUID
    status: str
    content_hash: str | None = None
    plain_text: str | None = None
    structured: StructuredResumeResponse | None = None
    parser_version: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    document: ResumeDocumentResponse | None = None


class ResumeSummaryResponse(BaseModel):
    id: UUID
    name: str
    status: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    latest_version_id: UUID | None = None
    parser_version: str | None = None


class ResumeDetailResponse(BaseModel):
    id: UUID
    name: str
    status: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    latest_version: ResumeVersionResponse | None = None
    signed_url: str | None = None
