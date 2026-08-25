# Local Development Infrastructure

Local Postgres (with **pgvector**) and Redis via Docker Compose. Run the API and Next.js web app on the host.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Python 3.11+ (3.14 works in current local setup)
- Node.js 20+ (for `apps/web`)
- A `.env` file at the repo root (copy from `.env.example`)

```bash
cp .env.example .env
```

Defaults:

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_USER` | `career` | Postgres role |
| `POSTGRES_PASSWORD` | `career` | Local-only password (change in real environments) |
| `POSTGRES_DB` | `career_agent` | Database name |
| `DATABASE_URL` | `postgresql://career:career@localhost:5433/career_agent` | App DB URL (host port **5433**) |
| `REDIS_URL` | `redis://localhost:6379/0` | App Redis URL |

## Start Postgres + Redis

From the **repository root**:

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d
```

Check containers:

```bash
docker ps
docker compose --env-file .env -f docker/docker-compose.yml ps
```

Healthy services should show `career-agent-db` (Postgres/pgvector on host port **5433**) and `career-agent-redis` (Redis on port **6379**). Host port 5433 avoids conflicting with a native Postgres install on 5432.

Apply migrations:

```bash
python -m alembic upgrade head
```

## Stop

Stop containers (keep data volumes):

```bash
docker compose --env-file .env -f docker/docker-compose.yml down
```

Stop and **delete volumes** (wipes local Postgres/Redis data):

```bash
docker compose --env-file .env -f docker/docker-compose.yml down -v
```

## Auth (Supabase) + API + Web

### 1. Configure Supabase Auth

In your Supabase project, enable Email auth. Put these in the **repo root** `.env`:

```bash
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key   # server-only; never ship to the browser

# Same public values for Next.js (also copy into apps/web/.env.local if preferred)
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

The API verifies access tokens with JWKS at `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`. **Do not set `SUPABASE_JWT_SECRET`.** Ensure your Supabase project publishes JWKS (asymmetric JWT signing).

For the web app, either:

```bash
cp apps/web/.env.example apps/web/.env.local
# fill NEXT_PUBLIC_* from root .env
```

or export the `NEXT_PUBLIC_*` variables in the shell before `npm run dev`.

### 2. Run the API

```bash
# from repo root — needs DATABASE_URL / REDIS_URL / SUPABASE_URL in .env
pip install -r requirements.txt
$env:PYTHONPATH=".;apps/api"   # PowerShell
# export PYTHONPATH=.:apps/api  # bash
uvicorn app.main:app --reload --app-dir apps/api --port 8000
```

Health (public): `GET http://localhost:8000/api/v1/health`  
Authenticated: `GET http://localhost:8000/api/v1/me` with `Authorization: Bearer <supabase_access_token>`

First successful authenticated call creates a local `users` row mapped by Supabase `sub` → `users.auth_subject`.

### 3. Run the web app

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000 — sign up / sign in, then `/dashboard` (protected). The dashboard calls `/api/v1/me` with the Supabase access token.

## Optional: self-hosted Firecrawl

Core Compose only runs Postgres and Redis. For scraping, run Firecrawl separately (or use an existing instance) and point the app at it:

```bash
# In .env — ScraperProvider talks to your instance via FIRECRAWL_BASE_URL
FIRECRAWL_BASE_URL=http://localhost:3002
# FIRECRAWL_API_KEY=   # only if your instance requires one
```

Do not assume the paid Firecrawl cloud API. Adapter code should use the same `ScraperProvider` interface regardless of where Firecrawl is hosted. A Firecrawl service is intentionally **not** part of `docker/docker-compose.yml` yet.

## Tests

```bash
# from repo root with Docker Postgres/Redis up and .env loaded
$env:PYTHONPATH=".;apps/api"
python -m pytest tests/test_auth.py tests/test_tenant_isolation.py tests/test_profile_preferences.py tests/test_resumes.py tests/test_tavily_search.py tests/test_firecrawl_scraper.py tests/test_llm_providers.py tests/test_job_discovery.py tests/test_job_match.py tests/test_jobs_api.py tests/test_discovery_worker.py tests/test_company_research.py -v
```

Auth tests use a **mocked JWT verifier** (no real Supabase network calls). Tenant isolation tests prove user A cannot read user B's jobs (job matches), applications, resumes, contacts, or outreach.

Profile and preferences endpoints are always scoped to the authenticated user (`GET/PUT /api/v1/profile`, `GET/PUT /api/v1/preferences`). The web app exposes `/profile` and `/preferences` pages that call these routes with the Supabase access token.

### Resumes (upload + structured parse)

Create a **private** Supabase Storage bucket (default name `resumes` via `SUPABASE_STORAGE_BUCKET`) and ensure `SUPABASE_SERVICE_ROLE_KEY` is set in the root `.env`. The API stores originals under `{user_id}/resumes/...` and returns signed URLs for download — no `SUPABASE_JWT_SECRET` is used.

```bash
# Extra deps for PDF/DOCX extraction (also in requirements.txt)
pip install PyMuPDF python-docx python-multipart
python -m alembic upgrade head   # adds resume_versions.parser_version
```

Authenticated endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/resumes` | Multipart upload (`file`, optional `name` / `description`) |
| `GET` | `/api/v1/resumes` | List own resumes |
| `GET` | `/api/v1/resumes/{id}` | Detail: extracted text, structured resume, signed URL |

The web app page is `/resumes` (nav link). Structured parsing is heuristic (`parser_version=heuristic-v1`); LLM parsing is optional later and not required for CI.

### Job discovery / matching (mocked in CI)

Domain services:

- `JobDiscoveryService` — preferences → search → scrape → LLM extract → validate → company → fingerprint/dedupe → `jobs` + `job_matches` + workflow events
- `JobMatchService` — deterministic scoring against preferences (no embeddings)
- `JobListingService` — tenant-scoped list/detail/rescore for API
- `DiscoveryTriggerService` — queues discovery workflow runs (async via Celery)

Authenticated job endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/jobs/discover` | Queue async discovery (returns `workflow_run_id` + Celery `task_id`) |
| `GET` | `/api/v1/jobs` | List own job matches with scores |
| `GET` | `/api/v1/jobs/{match_id}` | Detail with match breakdown, skills, explanation |
| `POST` | `/api/v1/jobs/{match_id}/score` | Re-score synchronously |
| `GET` | `/api/v1/workflows/{run_id}` | Discovery workflow status |

Web UI: `/jobs` (list + discover button), `/jobs/[id]` (detail + re-score).

### Celery worker (job discovery)

Install deps (includes `celery[redis]`):

```bash
pip install -r requirements.txt
```

Ensure Postgres + Redis are up, then from the **repo root**:

```bash
$env:PYTHONPATH=".;apps/api"   # PowerShell
celery -A workers.celery_app.celery_app worker --loglevel=info
```

The API enqueues `discover_jobs` on `POST /api/v1/jobs/discover`. Tests use `InlineDiscoveryTaskClient` (runs discovery in-process with mock providers when env keys are absent).

Provider adapters (real HTTP; CI uses mocks / monkeypatched HTTP):

- `TavilySearchProvider` (`TAVILY_API_KEY`)
- `FirecrawlScraperProvider` (`FIRECRAWL_BASE_URL`, optional `FIRECRAWL_API_KEY`)
- `GroqLLMProvider` / `GeminiLLMProvider` (`LLM_PROVIDER`, `GROQ_*` / `GEMINI_*`)

### Company + people research (mocked in CI)

- `CompanyResearchService` — search → scrape → LLM → cached `company_research`
- `PeopleResearchService` — role-priority people discovery (recruiter → … → referral); optional email enrich via EmailFinder/Verifier; never invents emails
- Optional real adapters: `ApolloPeopleProvider` (`APOLLO_API_KEY`), `HunterEmailFinderProvider` / `HunterEmailVerifierProvider` (`HUNTER_API_KEY`); mocks used when keys absent

### Application strategy / documents / engine (domain, mocked LLM/storage)

- `ApplicationStrategyService` — recommended actions + approvals (no send/submit)
- `ResumeCustomizationService` — tailor structured resume; rejects fabrications
- `render_resume_pdf` / `ResumePdfService` — deterministic ATS PDF via fixed template + StorageProvider upload
- `ApplicationContentService` — versioned prompts in `packages/prompts/application_content.py`
- `ApplicationEngine` — PREPARED → … → SUBMITTED state machine; SUBMITTED requires evidence
- `BrowserProvider` — mock for CI; optional `PlaywrightBrowserProvider` if Playwright installed
- `ATSAdapter` / `GreenhouseATSAdapter` — Greenhouse job-board forms via BrowserProvider (pause on CAPTCHA/unknown; submit only when permitted)
- `HumanTaskService` — CAPTCHA / unknown Q / login / approval pauses; `GET/POST /api/v1/human-tasks`
- `OutreachService` — DRAFT → approval → send via EmailSenderProvider; daily limits; never invents emails
- `EmailSenderProvider` — Resend when `RESEND_API_KEY` (+ `RESEND_FROM_EMAIL`) is set; otherwise mock (CI-safe). Optional SMTP fallback via `SMTP_HOST`; optional SES stub (not required)
- `MailboxProvider` — mock + encrypted token design; Gmail/Outlook stubs (no OAuth required)
- `CareerWorkflowService` — per-job pipeline with approval pause + resume; Celery workers for research/contacts/applications (+ stubs)

```bash
python -m pytest tests/test_auth.py tests/test_tenant_isolation.py tests/test_profile_preferences.py tests/test_resumes.py tests/test_tavily_search.py tests/test_firecrawl_scraper.py tests/test_llm_providers.py tests/test_job_discovery.py tests/test_job_match.py tests/test_jobs_api.py tests/test_discovery_worker.py tests/test_company_research.py tests/test_people_research.py tests/test_application_strategy.py tests/test_resume_customization.py tests/test_resume_pdf.py tests/test_application_content.py tests/test_browser_provider.py tests/test_application_engine.py tests/test_greenhouse_ats.py tests/test_human_tasks.py tests/test_outreach.py tests/test_email_mailbox.py tests/test_career_workflow.py -v
```

Web UI: `/tasks` for open human tasks. Mailbox status stub: `GET /api/v1/settings/mailbox`.

### Dashboard / SaaS UI (STEPs 30–34)

Authenticated Next.js pages (Tailwind; no business logic in React):

| Path | Purpose |
|------|---------|
| `/dashboard` | Summary counts + unread notifications + live SSE refresh |
| `/jobs`, `/jobs/[id]` | Matches + workspace (research, people, strategy, timeline) |
| `/applications`, `/applications/[id]` | Pipeline state, evidence, outreach, follow-ups, interviews/offers |
| `/contacts`, `/outreach`, `/interviews`, `/documents`, `/analytics` | List/detail surfaces |
| `/tasks` | Human tasks |
| `/settings` | Notifications + mailbox stub |
| `/profile`, `/preferences`, `/resumes` | Existing profile/prefs/resume flows |

New/expanded API (all tenant-scoped, Bearer auth):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/dashboard/summary` | Pipeline counts |
| `GET` | `/api/v1/jobs/{id}/workspace` | Job detail aggregation |
| `GET` | `/api/v1/applications` / `/{id}` | Enriched application list/detail |
| `GET` | `/api/v1/events/stream` | Authenticated SSE (Redis pub/sub) |
| `GET/POST` | `/api/v1/notifications` | List / mark read |
| `GET/POST` | `/api/v1/follow-ups` | Schedule + process due follow-ups |
| `GET/POST/PATCH` | `/api/v1/interviews`, `/api/v1/offers` | Interview & offer tracking |
| `GET` | `/api/v1/documents`, `/api/v1/analytics/summary` | Documents + analytics |

Domain services: `DashboardService`, `UserEventPublisher`, `NotificationService` (dedupe + optional Resend email), `FollowUpService`, `InterviewService`, `OfferService`.

```bash
python -m alembic upgrade head   # adds notifications.dedupe_key, follow_ups, interview fields
python -m pytest tests/test_saas_pipeline.py tests/test_outreach.py tests/test_human_tasks.py tests/test_career_workflow.py -v
```

### Celery workers (expanded)

```bash
$env:PYTHONPATH=".;apps/api"   # PowerShell
celery -A workers.celery_app.celery_app worker --loglevel=info
```

Registered task modules: discovery, research, contacts, documents, applications, outreach, notifications.

## Notes

- Passwords in `.env` / `.env.example` are for **local development only**. Do not reuse them in production.
- If you previously ran an older Compose file with a different `POSTGRES_USER`, recreate volumes with `down -v` before starting again so init scripts apply the new role/database.
- Enable the `vector` extension via Alembic (`CREATE EXTENSION IF NOT EXISTS vector;`) — the image includes pgvector but does not create the extension automatically.
- Auth (Supabase), LLM (Groq/Gemini), and storage (Supabase Storage) keys live in `.env.example`; for private storage buckets, object reads should use signed URLs generated server-side (so `SUPABASE_JWT_SECRET` is not needed for that assumption). `SUPABASE_STORAGE_PUBLIC_URL` is optional and only relevant for public buckets.
- Never put `SUPABASE_SERVICE_ROLE_KEY` in `NEXT_PUBLIC_*` or commit real secrets.
