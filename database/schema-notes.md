# Database Schema Notes

Design documentation for the AI Career Agent PostgreSQL schema. **No SQL in this document** — migrations will be derived from these notes in a later step.

## Conventions

- **Tenant isolation**: User-owned entities include a `user_id` (or equivalent) foreign key. Queries for user data must always filter by tenant.
- **Shared reference data**: Entities like `companies`, `people`, and `jobs` may be shared across tenants when ingested from public sources; tenant-specific views and actions are modeled in separate tables (`job_matches`, `company_research`, `contacts`).
- **Auditability**: State changes on critical entities should produce rows in `application_events`, `outreach_events`, `audit_logs`, or `workflow_tasks` as appropriate.
- **Status fields**: Use explicit enums/constrained text values; transitions should be validated in domain services.

---

## users

**One row represents:** A single authenticated account in the system.

**Ownership / tenant:** Root tenant entity. Each user is their own tenant boundary for user-owned data.

**Auth mapping:** `auth_subject` stores the Supabase Auth user id (`sub` claim). Created on first authenticated API request. JWT verification uses Supabase JWKS (no shared JWT secret in app config).

**Important relationships:**
- One-to-one (or one-to-few) with `user_profiles`, `user_preferences`.
- One-to-many with nearly all tenant-scoped tables (`applications`, `resumes`, `job_matches`, `workflow_runs`, etc.).

**Lifecycle / status:**
- `active` — normal operation.
- `suspended` — login blocked; data retained.
- `deleted` — soft-deleted; PII may be anonymized per retention policy.

---

## user_profiles

**One row represents:** Canonical profile information for a user (display name, headline, location, LinkedIn URL, summary, etc.).

**Ownership / tenant:** Owned by exactly one `user_id`. Tenant-isolated.

**Important relationships:**
- Belongs to `users`.
- May inform resume generation and application answers but is not a substitute for verified resume content.

**Lifecycle / status:**
- `active` — current profile in use.
- Superseded profiles, if versioned, would be archived rather than overwritten silently.

---

## user_preferences

**One row represents:** Configurable preferences for job search, notifications, automation, and UI behavior for one user.

**Ownership / tenant:** Owned by exactly one `user_id`. Tenant-isolated.

**Important relationships:**
- Belongs to `users`.
- May reference automation rules that govern `outreach` auto-send and `human_tasks` bypass conditions (explicit rules only).

**Lifecycle / status:**
- `active` — preferences in effect.
- Updated in place; significant changes should be auditable via `audit_logs`.

---

## resumes

**One row represents:** A logical resume document owned by a user (e.g., "Software Engineering Master Resume").

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- One-to-many with `resume_versions` (each version is an immutable or semi-immutable snapshot).
- Referenced by `applications` via a specific `resume_version_id`.

**Lifecycle / status:**
- `active` — available for tailoring and applications.
- `archived` — no longer used for new applications but retained for history.

---

## resume_versions

**One row represents:** A specific version or snapshot of a resume (content hash, structured sections, plain text, file reference).

**Ownership / tenant:** Owned by `user_id` (via `resumes`). Tenant-isolated.

**Important relationships:**
- Belongs to `resumes`.
- May link to a `documents` row for stored file (PDF/DOCX).
- Referenced by `applications` when a tailored resume is submitted.

**Lifecycle / status:**
- `draft` — being edited or generated; not submission-ready.
- `finalized` — approved for use in applications.
- `superseded` — replaced by a newer version.

---

## documents

**One row represents:** A stored document artifact (resume file, cover letter, portfolio excerpt, application attachment).

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- May belong to a `resume_version`, `application`, or stand alone.
- Stored metadata: filename, mime type, storage path/URL, checksum.

**Lifecycle / status:**
- `draft` — generated or uploaded but not finalized.
- `final` — approved for submission or sending.
- `archived` — retained for audit but not actively used.

---

## companies

**One row represents:** An employer organization (legal or common name, primary website, industry tags).

**Ownership / tenant:** **Shared reference data** — not tenant-owned. Multiple users may reference the same company. Tenant-specific research lives in `company_research`.

**Important relationships:**
- One-to-many with `company_domains`, `people_roles`, `jobs`.
- Referenced by `company_research`, `contacts`, and `applications` (indirectly via jobs).

**Lifecycle / status:**
- `active` — known valid entity.
- `merged` — absorbed into another company (link to successor).
- `inactive` — defunct; retained for historical applications.

---

## company_domains

**One row represents:** A known web or email domain associated with a company (e.g., `acme.com`).

**Ownership / tenant:** Shared reference data linked to `companies`.

**Important relationships:**
- Belongs to `companies`.
- Used for email verification heuristics and contact validation (never to invent addresses).

**Lifecycle / status:**
- `verified` — confirmed association with company.
- `unverified` — ingested but not confirmed.
- `deprecated` — domain no longer in use.

---

## company_research

**One row represents:** A research artifact or summary about a company for a specific user (culture notes, funding, tech stack, interview tips).

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- Belongs to `users` and `companies`.
- May be produced by a `workflow_run` in the research worker.
- Content is **untrusted scraped input** — must not override system instructions.

**Lifecycle / status:**
- `in_progress` — research job running.
- `complete` — research available for review.
- `stale` — older than freshness threshold; refresh recommended.

---

## job_sources

**One row represents:** A configured source for job discovery (board name, API/scrape config, search parameters).

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- Belongs to `users`.
- One-to-many with `jobs` (jobs ingested from this source for this user).

**Lifecycle / status:**
- `active` — included in discovery runs.
- `paused` — temporarily excluded.
- `error` — last sync failed; requires attention.

---

## jobs

**One row represents:** A single job posting (title, description, location, salary range, posting URL, external ID).

**Ownership / tenant:** **Hybrid.** Ingested jobs may be shared (deduplicated by URL/external ID) or scoped per user depending on source. At minimum, `job_matches` provides the tenant-specific view. If per-tenant duplication is used, include `user_id` on `jobs`; otherwise enforce access only through `job_matches`.

**Important relationships:**
- Belongs to `companies` (employer).
- Optional link to `job_sources`.
- One-to-many with `job_matches`, `applications`.

**Lifecycle / status:**
- `active` — open and accepting applications.
- `closed` — explicitly closed by employer.
- `expired` — past deadline or removed from source.
- `archived` — retained for history only.

---

## job_matches

**One row represents:** A user's evaluated match against a job (score, ranking, fit summary, user decision).

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- Belongs to `users` and `jobs`.
- May precede an `applications` row when the user decides to apply.
- May be produced by discovery/research workflows.

**Lifecycle / status:**
- `new` — surfaced, not yet reviewed.
- `reviewed` — user has seen it.
- `saved` — user flagged for later.
- `dismissed` — user rejected.
- `applied` — linked to an application (or subsumed when application is created).

---

## people

**One row represents:** A person identity (name, public profile URLs) independent of any single user relationship.

**Ownership / tenant:** **Shared reference data** — same person may be referenced by multiple users' `contacts`. PII handling must respect privacy and consent.

**Important relationships:**
- One-to-many with `people_roles` (employment history at companies).
- Referenced by `contacts`.

**Lifecycle / status:**
- `active` — valid known person.
- `merged` — duplicate resolved into another `people` row.

---

## people_roles

**One row represents:** A person's role or title at a company for a period (e.g., "Recruiter at Acme, 2022–present").

**Ownership / tenant:** Shared reference data linking `people` and `companies`.

**Important relationships:**
- Belongs to `people` and `companies`.

**Lifecycle / status:**
- `current` — ongoing role.
- `former` — ended role.

---

## contacts

**One row represents:** A user's relationship to a person for networking or outreach (not merely a global identity).

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- Belongs to `users` and `people`.
- Optional links to `companies`, `applications`, or `jobs` for context.
- One-to-many with `contact_sources`, `email_verifications`, `outreach`.

**Lifecycle / status:**
- `identified` — known but not verified.
- `verified` — contact channel confirmed.
- `do_not_contact` — user or compliance block on outreach.

---

## contact_sources

**One row represents:** Provenance for contact information (where an email, LinkedIn URL, or phone number was obtained).

**Ownership / tenant:** Owned by `user_id` (via `contacts`). Tenant-isolated.

**Important relationships:**
- Belongs to `contacts`.
- Supports audit: scraped page URL, manual entry, API provider, timestamp.

**Lifecycle / status:**
- Immutable audit record once created.
- Source type: `manual`, `scrape`, `provider_api`, `inferred` (inferred must never be treated as verified).

---

## email_verifications

**One row represents:** A verification attempt or result for an email address associated with a contact or person.

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- Links to `contacts` or `people`.
- Informs whether outreach may proceed (never invent emails — verification only).

**Lifecycle / status:**
- `pending` — verification in progress.
- `verified` — deliverable and confirmed.
- `invalid` — undeliverable or rejected.
- `catch_all` — domain accepts all mail; lower confidence.
- `unknown` — could not determine.

---

## applications

**One row represents:** A user's pursuit of a specific job — one application per user per job.

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- Belongs to `users` and `jobs`.
- References a `resume_version_id` and optional `documents` (cover letter).
- One-to-many with `application_events`, `application_answers`, `interviews`, `offers`, `outreach`.
- Unique constraint: (`user_id`, `job_id`).

**Lifecycle / status:**
- `draft` — preparing materials, not submitted.
- `in_progress` — submission workflow running.
- `submitted` — **only with explicit submission evidence** (confirmation email, portal screenshot metadata, application ID from employer).
- `under_review` — employer acknowledged receipt.
- `rejected` — employer declined.
- `withdrawn` — user withdrew.
- `offer` — moved to offer stage (see `offers`).

---

## application_events

**One row represents:** An immutable timeline event on an application (status change, note, portal update, email received).

**Ownership / tenant:** Owned by `user_id` (via `applications`). Tenant-isolated.

**Important relationships:**
- Belongs to `applications`.
- May reference `workflow_tasks` or external evidence IDs.

**Lifecycle / status:**
- Append-only audit log. Event types: `status_changed`, `note_added`, `document_attached`, `submission_confirmed`, `email_received`, etc.

---

## application_answers

**One row represents:** An answer to a specific application question (screening question, work authorization, custom essay).

**Ownership / tenant:** Owned by `user_id` (via `applications`). Tenant-isolated.

**Important relationships:**
- Belongs to `applications`.
- Content must be validated; no fabricated experience or metrics.

**Lifecycle / status:**
- `draft` — generated or edited, not yet submitted.
- `approved` — user approved for submission.
- `submitted` — included in submitted application payload.

---

## outreach

**One row represents:** A planned or sent communication to a contact (email, LinkedIn message, follow-up sequence step).

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- Belongs to `users`, `contacts`.
- Optional link to `applications` for context.
- One-to-many with `outreach_events`.
- Requires user approval unless an explicit automation rule in `user_preferences` allows send.

**Lifecycle / status:**
- `draft` — composed, not approved.
- `pending_approval` — awaiting user or `human_tasks` approval.
- `approved` — cleared to send.
- `sent` — delivered to provider.
- `replied` — response received.
- `bounced` — delivery failed.
- `cancelled` — not sent.

---

## outreach_events

**One row represents:** An immutable event on an outreach record (sent, delivered, opened, clicked, replied, bounced).

**Ownership / tenant:** Owned by `user_id` (via `outreach`). Tenant-isolated.

**Important relationships:**
- Belongs to `outreach`.

**Lifecycle / status:**
- Append-only. Events recorded with provider timestamps and raw payload references.

---

## interviews

**One row represents:** A single interview round or interaction for an application.

**Ownership / tenant:** Owned by `user_id` (via `applications`). Tenant-isolated.

**Important relationships:**
- Belongs to `applications`.
- May reference `contacts` (interviewer) or `people`.

**Lifecycle / status:**
- `scheduled` — date/time confirmed.
- `completed` — interview occurred.
- `cancelled` — cancelled by either party.
- `no_show` — participant absent.
- `rescheduled` — linked to a new interview row or updated schedule.

---

## offers

**One row represents:** A job offer extended to the user for an application.

**Ownership / tenant:** Owned by `user_id` (via `applications`). Tenant-isolated.

**Important relationships:**
- Belongs to `applications`.
- May reference a `documents` row for offer letter storage.

**Lifecycle / status:**
- `pending` — offer received, decision not made.
- `accepted` — user accepted.
- `declined` — user declined.
- `expired` — deadline passed.
- `rescinded` — employer withdrew offer.

---

## notifications

**One row represents:** An in-app or deliverable notification for a user.

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- Belongs to `users`.
- May reference `applications`, `outreach`, `human_tasks`, or `workflow_runs` as context.

**Lifecycle / status:**
- `unread` — not yet seen.
- `read` — user acknowledged.
- `dismissed` — cleared from active UI.

---

## workflow_runs

**One row represents:** A single execution of a multi-step workflow (discovery sync, company research batch, document generation job).

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- Belongs to `users`.
- One-to-many with `workflow_tasks`.
- May produce or update `job_matches`, `company_research`, `documents`, etc.

**Lifecycle / status:**
- `queued` — waiting for worker.
- `running` — in progress.
- `completed` — all tasks finished successfully.
- `failed` — unrecoverable error.
- `cancelled` — stopped by user or system.

---

## workflow_tasks

**One row represents:** An individual step within a workflow run (scrape page, call LLM, persist results).

**Ownership / tenant:** Owned by `user_id` (via `workflow_runs`). Tenant-isolated.

**Important relationships:**
- Belongs to `workflow_runs`.
- May link to `provider_usage` for cost tracking.

**Lifecycle / status:**
- `pending` — not started.
- `running` — executing.
- `completed` — success.
- `failed` — error with retry policy.
- `skipped` — intentionally bypassed.

---

## provider_usage

**One row represents:** A record of a call to an external provider (LLM, Tavily, Firecrawl, storage, email API, etc.) for metering and audit.

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- Belongs to `users`.
- Optional links to `workflow_tasks`, `workflow_runs`.

**Lifecycle / status:**
- Append-only usage log. Fields: provider name, operation, token/credit counts, cost estimate, latency, success/failure.

---

## audit_logs

**One row represents:** A system-wide or user-scoped audit record for security-sensitive or compliance-relevant actions.

**Ownership / tenant:** Scoped by `user_id` when action is user-initiated; may be `NULL` for system events.

**Important relationships:**
- May reference any entity type via polymorphic (`entity_type`, `entity_id`) pattern.

**Lifecycle / status:**
- Append-only, immutable. Includes actor (user/system), action, timestamp, IP/session metadata, before/after snapshots as needed.

---

## human_tasks

**One row represents:** A task requiring explicit human action or approval (approve outreach, review fabricated-risk content, complete CAPTCHA manually).

**Ownership / tenant:** Owned by `user_id`. Tenant-isolated.

**Important relationships:**
- Belongs to `users`.
- May block `outreach`, `applications`, or `workflow_runs` until resolved.
- Distinct from `notifications` — tasks are actionable work items; notifications are informational.

**Lifecycle / status:**
- `open` — awaiting action.
- `in_progress` — user is working on it.
- `completed` — resolved.
- `cancelled` — no longer needed.

---

## Entity Relationship Summary

```
users
 ├── user_profiles, user_preferences
 ├── resumes → resume_versions → documents
 ├── job_sources → jobs (via ingestion)
 ├── job_matches → jobs
 ├── company_research → companies
 ├── contacts → people → people_roles → companies
 │              → contact_sources, email_verifications
 ├── applications → jobs
 │                → application_events, application_answers
 │                → interviews, offers, outreach
 ├── outreach → outreach_events
 ├── notifications, human_tasks
 ├── workflow_runs → workflow_tasks → provider_usage
 └── audit_logs

companies → company_domains, jobs, people_roles
```

---

## Schema Review — Issues and Open Questions

The following items were identified during self-review. **Not redesigned automatically** — to be resolved when writing migrations.

1. **Legacy `emails` table vs `outreach` / `outreach_events`:** The existing prototype schema (`database/schema.sql`) has an `emails` table tied to applications. The new model splits message intent (`outreach`) from delivery events (`outreach_events`). A migration strategy must map or drop legacy data.

2. **Legacy `resumes` linked directly to `applications`:** The new model introduces `resumes` → `resume_versions` → `applications`. The old schema stores resumes per application without versioning. Migration must restructure or archive old rows.

3. **`jobs` tenant scoping ambiguity:** Notes describe hybrid shared/per-tenant jobs. A concrete decision is needed: either (a) global `jobs` with mandatory `job_matches` for access control, or (b) per-tenant `jobs` with deduplication keys. Without this, duplicate job rows across users are possible.

4. **`people` vs `contacts` boundary:** Shared `people` identities with tenant-scoped `contacts` is clear conceptually, but deduplication/merge rules for the same person across users are undefined.

5. **`documents` vs `resume_versions` overlap:** Both can store file artifacts. Clarify whether every resume version must have a document row or if inline content on `resume_versions` is sufficient.

6. **`notifications` vs `human_tasks` overlap:** Both can signal "action needed." Domain rules should define when an approval creates a `human_task` vs a `notification` vs both.

7. **Missing explicit `user_id` on legacy shared tables:** Existing prototype tables (`companies`, `jobs`, `applications`, `contacts`) have no tenant column — incompatible with rule 9 (tenant isolation). All user-owned paths need `user_id` or equivalent.

8. **`job_matches.applied` vs `applications` creation:** Transition rule needed: does creating an application auto-update match status, or are these independent?

9. **`company_research` freshness:** `stale` status threshold and refresh triggers are unspecified.

10. **Submission evidence model:** `applications.submitted` requires evidence, but no dedicated `submission_evidence` entity exists — may be stored as `application_events` or `documents`; consider explicit structure later.

11. **Automation rules storage:** Rules allowing outreach without per-message approval are referenced in `user_preferences` but not modeled as first-class entities — may become unwieldy as JSON.

12. **No explicit CAPTCHA / manual intervention entity:** `human_tasks` covers this generically; task type taxonomy not yet defined.

13. **Polymorphic references in `audit_logs`:** Flexible but harder to enforce referential integrity — acceptable tradeoff if documented.

14. **Shared `companies` / `jobs` write contention:** Multiple users ingesting the same employer or posting need idempotent upsert keys (URL, external ID) defined at migration time.
