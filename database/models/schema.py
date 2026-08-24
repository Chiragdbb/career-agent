from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from database.models.base import Base, UUIDMixin, TimestampMixin
from database.models.enums import (
    ApplicationAnswerStatus,
    ApplicationStatus,
    CompanyDomainStatus,
    CompanyResearchStatus,
    CompanyStatus,
    ContactSourceType,
    ContactStatus,
    DocumentStatus,
    EmailVerificationStatus,
    HumanTaskStatus,
    InterviewStatus,
    JobMatchStatus,
    JobSourceStatus,
    JobStatus,
    NotificationStatus,
    OfferStatus,
    PeopleRoleStatus,
    PeopleStatus,
    ResumeStatus,
    ResumeVersionStatus,
    OutreachStatus,
    UserPreferenceStatus,
    UserProfileStatus,
    UserStatus,
    WorkflowRunStatus,
    WorkflowTaskStatus,
)

# Models are derived from database/schema-notes.md.
# schema-notes.md focuses on entities/relationships/statuses rather than full
# column-level detail; fields below include only what schema-notes.md names.


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Supabase Auth subject (`sub` claim). Maps external identity → local tenant.
    auth_subject = sa.Column(sa.Text, nullable=False, unique=True, index=True)

    status = sa.Column(
        sa.Enum(UserStatus, name="user_status"),
        nullable=False,
        default=UserStatus.active,
    )


class UserProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_profiles"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    status = sa.Column(
        sa.Enum(UserProfileStatus, name="user_profile_status"),
        nullable=False,
        default=UserProfileStatus.active,
    )

    display_name = sa.Column(sa.Text)
    headline = sa.Column(sa.Text)
    location = sa.Column(sa.Text)
    linkedin_url = sa.Column(sa.Text)
    summary = sa.Column(sa.Text)


class UserPreference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_preferences"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    status = sa.Column(
        sa.Enum(UserPreferenceStatus, name="user_preference_status"),
        nullable=False,
        default=UserPreferenceStatus.active,
    )

    settings = sa.Column(sa.dialects.postgresql.JSONB)


class Resume(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "resumes"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(ResumeStatus, name="resume_status"),
        nullable=False,
        default=ResumeStatus.active,
    )

    name = sa.Column(sa.Text, nullable=False)
    description = sa.Column(sa.Text)


class ResumeVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "resume_versions"

    resume_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(ResumeVersionStatus, name="resume_version_status"),
        nullable=False,
        default=ResumeVersionStatus.draft,
    )

    content_hash = sa.Column(sa.Text)
    plain_text = sa.Column(sa.Text)
    sections = sa.Column(sa.dialects.postgresql.JSONB)


class Document(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(DocumentStatus, name="document_status"),
        nullable=False,
        default=DocumentStatus.draft,
    )

    filename = sa.Column(sa.Text)
    mime_type = sa.Column(sa.Text)
    storage_path = sa.Column(sa.Text)
    checksum = sa.Column(sa.Text)

    resume_version_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("resume_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    application_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("applications.id", ondelete="SET NULL", use_alter=True, name="fk_documents_application_id"),
        nullable=True,
        index=True,
    )


class Company(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    status = sa.Column(
        sa.Enum(CompanyStatus, name="company_status"),
        nullable=False,
        default=CompanyStatus.active,
    )

    name = sa.Column(sa.Text, nullable=False)
    url = sa.Column(sa.Text)


class CompanyDomain(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "company_domains"

    company_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    domain = sa.Column(sa.Text, nullable=False, unique=True)

    status = sa.Column(
        sa.Enum(CompanyDomainStatus, name="company_domain_status"),
        nullable=False,
        default=CompanyDomainStatus.verified,
    )


class CompanyResearch(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "company_research"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(CompanyResearchStatus, name="company_research_status"),
        nullable=False,
        default=CompanyResearchStatus.in_progress,
    )

    summary = sa.Column(sa.Text)
    data = sa.Column(sa.dialects.postgresql.JSONB)


class JobSource(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "job_sources"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(JobSourceStatus, name="job_source_status"),
        nullable=False,
        default=JobSourceStatus.active,
    )

    name = sa.Column(sa.Text, nullable=False)
    config = sa.Column(sa.dialects.postgresql.JSONB)
    last_error = sa.Column(sa.Text)


class Job(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    company_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(JobStatus, name="job_status"),
        nullable=False,
        default=JobStatus.active,
    )

    title = sa.Column(sa.Text, nullable=False)
    url = sa.Column(sa.Text)
    external_id = sa.Column(sa.Text)
    description = sa.Column(sa.Text)
    posted_at = sa.Column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("url", name="uq_jobs_url"),
        sa.UniqueConstraint("external_id", name="uq_jobs_external_id"),
    )


class JobMatch(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "job_matches"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(JobMatchStatus, name="job_match_status"),
        nullable=False,
        default=JobMatchStatus.new,
    )

    score = sa.Column(sa.Float)
    rank = sa.Column(sa.Integer)
    fit_summary = sa.Column(sa.Text)
    decision_note = sa.Column(sa.Text)

    __table_args__ = (
        sa.UniqueConstraint("user_id", "job_id", name="uq_job_matches_user_job"),
        sa.Index("ix_job_matches_user_status", "user_id", "status"),
    )


class Person(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "people"

    status = sa.Column(
        sa.Enum(PeopleStatus, name="people_status"),
        nullable=False,
        default=PeopleStatus.active,
    )

    name = sa.Column(sa.Text, nullable=False)
    linkedin_url = sa.Column(sa.Text)


class PeopleRole(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "people_roles"

    people_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(PeopleRoleStatus, name="people_role_status"),
        nullable=False,
        default=PeopleRoleStatus.current,
    )

    role_title = sa.Column(sa.Text)
    start_date = sa.Column(sa.Date)
    end_date = sa.Column(sa.Date)


class Contact(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "contacts"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    people_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    company_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = sa.Column(
        sa.Enum(ContactStatus, name="contact_status"),
        nullable=False,
        default=ContactStatus.identified,
    )

    name = sa.Column(sa.Text)
    title = sa.Column(sa.Text)


class ContactSource(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "contact_sources"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    contact_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_type = sa.Column(
        sa.Enum(ContactSourceType, name="contact_source_type"),
        nullable=False,
        default=ContactSourceType.manual,
    )

    source_url = sa.Column(sa.Text)
    metadata_json = sa.Column(sa.dialects.postgresql.JSONB)


class EmailVerification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "email_verifications"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    contact_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    email = sa.Column(sa.Text, nullable=False)

    status = sa.Column(
        sa.Enum(EmailVerificationStatus, name="email_verification_status"),
        nullable=False,
        default=EmailVerificationStatus.pending,
    )

    verified_at = sa.Column(sa.DateTime(timezone=True))
    details = sa.Column(sa.dialects.postgresql.JSONB)


class Application(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "applications"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(ApplicationStatus, name="application_status"),
        nullable=False,
        default=ApplicationStatus.draft,
    )

    applied_at = sa.Column(sa.DateTime(timezone=True))

    resume_version_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("resume_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    cover_letter_document_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    submission_evidence = sa.Column(sa.dialects.postgresql.JSONB)

    __table_args__ = (
        sa.UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),
    )


class ApplicationEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "application_events"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type = sa.Column(sa.Text, nullable=False)
    payload = sa.Column(sa.dialects.postgresql.JSONB)


class ApplicationAnswer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "application_answers"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    application_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(ApplicationAnswerStatus, name="application_answer_status"),
        nullable=False,
        default=ApplicationAnswerStatus.draft,
    )

    question_key = sa.Column(sa.Text)
    answer_text = sa.Column(sa.Text)


class Outreach(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "outreach"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    contact_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    application_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = sa.Column(
        sa.Enum(OutreachStatus, name="outreach_status"),
        nullable=False,
        default=OutreachStatus.draft,
    )

    channel = sa.Column(sa.Text)
    subject = sa.Column(sa.Text)
    body = sa.Column(sa.Text)


class OutreachEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "outreach_events"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    outreach_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("outreach.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type = sa.Column(sa.Text, nullable=False)
    provider_event_id = sa.Column(sa.Text)
    provider_timestamp = sa.Column(sa.DateTime(timezone=True))
    payload = sa.Column(sa.dialects.postgresql.JSONB)


class Interview(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "interviews"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    application_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(InterviewStatus, name="interview_status"),
        nullable=False,
        default=InterviewStatus.scheduled,
    )

    title = sa.Column(sa.Text)
    scheduled_at = sa.Column(sa.DateTime(timezone=True))
    notes = sa.Column(sa.Text)


class Offer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "offers"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    application_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(OfferStatus, name="offer_status"),
        nullable=False,
        default=OfferStatus.pending,
    )

    offer_deadline = sa.Column(sa.DateTime(timezone=True))
    details = sa.Column(sa.dialects.postgresql.JSONB)


class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(NotificationStatus, name="notification_status"),
        nullable=False,
        default=NotificationStatus.unread,
    )

    notification_type = sa.Column(sa.Text)
    title = sa.Column(sa.Text)
    body = sa.Column(sa.Text)
    data = sa.Column(sa.dialects.postgresql.JSONB)


class WorkflowRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(WorkflowRunStatus, name="workflow_run_status"),
        nullable=False,
        default=WorkflowRunStatus.queued,
    )

    workflow_type = sa.Column(sa.Text, nullable=False)
    metadata_json = sa.Column(sa.dialects.postgresql.JSONB)
    error = sa.Column(sa.Text)


class WorkflowTask(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workflow_tasks"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    workflow_run_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(WorkflowTaskStatus, name="workflow_task_status"),
        nullable=False,
        default=WorkflowTaskStatus.pending,
    )

    task_type = sa.Column(sa.Text, nullable=False)
    input_payload = sa.Column(sa.dialects.postgresql.JSONB)
    output_payload = sa.Column(sa.dialects.postgresql.JSONB)
    error = sa.Column(sa.Text)
    attempt = sa.Column(sa.Integer)


class ProviderUsage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "provider_usage"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    workflow_run_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    workflow_task_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("workflow_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    provider_name = sa.Column(sa.Text, nullable=False)
    operation = sa.Column(sa.Text, nullable=False)

    token_count = sa.Column(sa.BigInteger)
    credit_count = sa.Column(sa.Float)
    cost_estimate = sa.Column(sa.Float)
    latency_ms = sa.Column(sa.Integer)

    success = sa.Column(sa.Boolean, nullable=False, default=True)
    error = sa.Column(sa.Text)
    payload = sa.Column(sa.dialects.postgresql.JSONB)


class AuditLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    actor_type = sa.Column(sa.Text, nullable=False, default="system")
    action = sa.Column(sa.Text, nullable=False)

    entity_type = sa.Column(sa.Text)
    entity_id = sa.Column(PG_UUID(as_uuid=True))

    ip_address = sa.Column(sa.Text)
    session_id = sa.Column(sa.Text)

    before = sa.Column(sa.dialects.postgresql.JSONB)
    after = sa.Column(sa.dialects.postgresql.JSONB)
    metadata_json = sa.Column(sa.dialects.postgresql.JSONB)


class HumanTask(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "human_tasks"

    user_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = sa.Column(
        sa.Enum(HumanTaskStatus, name="human_task_status"),
        nullable=False,
        default=HumanTaskStatus.open,
    )

    task_type = sa.Column(sa.Text, nullable=False)
    title = sa.Column(sa.Text)
    details = sa.Column(sa.dialects.postgresql.JSONB)

    blocking_entity_type = sa.Column(sa.Text)
    blocking_entity_id = sa.Column(PG_UUID(as_uuid=True))

    outreach_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("outreach.id", ondelete="SET NULL"),
        nullable=True,
    )

    application_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
    )

    workflow_run_id = sa.Column(
        PG_UUID(as_uuid=True),
        sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
