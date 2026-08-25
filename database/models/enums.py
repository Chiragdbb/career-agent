from __future__ import annotations

import enum


class UserStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    deleted = "deleted"


class UserProfileStatus(str, enum.Enum):
    active = "active"


class UserPreferenceStatus(str, enum.Enum):
    active = "active"


class ResumeStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class ResumeVersionStatus(str, enum.Enum):
    draft = "draft"
    finalized = "finalized"
    superseded = "superseded"


class DocumentStatus(str, enum.Enum):
    draft = "draft"
    final = "final"
    archived = "archived"


class CompanyStatus(str, enum.Enum):
    active = "active"
    merged = "merged"
    inactive = "inactive"


class CompanyDomainStatus(str, enum.Enum):
    verified = "verified"
    unverified = "unverified"
    deprecated = "deprecated"


class CompanyResearchStatus(str, enum.Enum):
    in_progress = "in_progress"
    complete = "complete"
    stale = "stale"


class JobSourceStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    error = "error"


class JobStatus(str, enum.Enum):
    active = "active"
    closed = "closed"
    expired = "expired"
    archived = "archived"


class JobMatchStatus(str, enum.Enum):
    new = "new"
    reviewed = "reviewed"
    saved = "saved"
    dismissed = "dismissed"
    applied = "applied"


class PeopleStatus(str, enum.Enum):
    active = "active"
    merged = "merged"


class PeopleRoleStatus(str, enum.Enum):
    current = "current"
    former = "former"


class ContactStatus(str, enum.Enum):
    identified = "identified"
    verified = "verified"
    do_not_contact = "do_not_contact"


class ContactSourceType(str, enum.Enum):
    manual = "manual"
    scrape = "scrape"
    provider_api = "provider_api"
    inferred = "inferred"


class EmailVerificationStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    invalid = "invalid"
    catch_all = "catch_all"
    unknown = "unknown"


class ApplicationStatus(str, enum.Enum):
    draft = "draft"
    in_progress = "in_progress"
    submitted = "submitted"
    under_review = "under_review"
    rejected = "rejected"
    withdrawn = "withdrawn"
    offer = "offer"


class ApplicationAnswerStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    submitted = "submitted"


class OutreachStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    sent = "sent"
    replied = "replied"
    bounced = "bounced"
    cancelled = "cancelled"


class InterviewStatus(str, enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"
    rescheduled = "rescheduled"


class OfferStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"
    rescinded = "rescinded"


class NotificationStatus(str, enum.Enum):
    unread = "unread"
    read = "read"
    dismissed = "dismissed"


class FollowUpStatus(str, enum.Enum):
    scheduled = "scheduled"
    pending_approval = "pending_approval"
    sent = "sent"
    cancelled = "cancelled"
    completed = "completed"


class WorkflowRunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class WorkflowTaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class HumanTaskStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
