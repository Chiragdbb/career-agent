# Production Deployment

This document describes how to deploy Career Agent. **Deploy credentials / cloud
accounts are HUMAN INPUT** — CI and docs are provided; live deploy is not
automated until secrets exist.

## Recommended topology

| Component | Suggested host | Notes |
|-----------|----------------|-------|
| Frontend (`apps/web`) | Vercel | Next.js; set `NEXT_PUBLIC_*` |
| API (`apps/api`) | Render / Fly / AWS | Bind `0.0.0.0:$PORT` |
| Workers (Celery) | Optional / legacy | Only if `TASK_BACKEND=celery` |
| QStash schedules | Upstash | Daily discovery → `/internal/qstash/scheduled-discover` |
| PostgreSQL + pgvector | Managed Postgres | Enable `vector` extension |
| Redis | Managed Redis | SSE / EventBus (not required as Celery broker for discovery) |
| Object storage | Supabase Storage | Private bucket + signed URLs |

## Prerequisites (manual)

Create accounts / resources and store secrets in the host’s secret manager
(never commit them):

- Supabase project (Auth JWKS + Storage)
- Managed Postgres with pgvector
- Managed Redis
- Provider keys as needed: Groq/Gemini/OpenAI, Tavily, Firecrawl, Resend, …
- Optional: `SENTRY_DSN`, `POSTHOG_API_KEY`, `NOTION_API_KEY`
- Domain + HTTPS certificates

See [`.env.example`](../.env.example) and the Environment variables section below for the full checklist.

## Build & run (containers)

API example:

```bash
pip install -r requirements.txt
export PYTHONPATH=".:apps/api"
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir apps/api
```

### Render (API web service)

- **Start command** (typical): `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --app-dir apps/api` with `PYTHONPATH=.:apps/api`.
- **Health check**: leave the default path as `/` (the API answers `GET`/`HEAD /` with 200) or set **Health Check Path** to `/health`. Do not point Render at `/api/v1/health` unless you prefer the full DB/Redis check during deploys.
- **Startup time**: migrations plus Python imports can take 30–60s before the port opens; if deploys still time out, increase the service health-check grace period in the Render dashboard.

Worker:

```bash
export PYTHONPATH=".:apps/api"
celery -A workers.celery_app.celery_app worker --loglevel=info
```

Beat (legacy Celery scheduled discovery — prefer QStash in production):

```bash
export PYTHONPATH=".:apps/api"
celery -A workers.celery_app.celery_app beat --loglevel=info
```

## QStash discovery (production)

Discovery enqueue and the daily schedule run through Upstash QStash HTTP
callbacks into the API (no Celery worker/beat required for this path).

1. On Render (API service), set:
   - `TASK_BACKEND=qstash`
   - `QSTASH_TOKEN` (publish token from Upstash console)
   - `QSTASH_CURRENT_SIGNING_KEY` / optional `QSTASH_NEXT_SIGNING_KEY`
   - `QSTASH_CALLBACK_BASE_URL=https://career-agent-api-05z9.onrender.com`
     (no trailing slash; must match the public HTTPS URL QStash calls)
2. In the Upstash QStash console, create a **daily** schedule that
   `POST`s to:
   `{QSTASH_CALLBACK_BASE_URL}/internal/qstash/scheduled-discover`
   (empty JSON body is fine). QStash signs requests; the API verifies
   `Upstash-Signature` before running work.
3. **Redis is still required** for SSE / EventBus pub/sub even when
   discovery uses QStash instead of Celery as the broker.

Callback routes (not under `/api/v1`):

| Method | Path | Action |
|--------|------|--------|
| POST | `/internal/qstash/discover-jobs` | Run `_run_discovery` |
| POST | `/internal/qstash/rescrape-job` | Run `_run_rescrape` |
| POST | `/internal/qstash/scheduled-discover` | Fan-out discovery for active users |

Never put `QSTASH_TOKEN` or signing keys in `NEXT_PUBLIC_*` or the web app.

Web:

```bash
cd apps/web && npm ci && npm run build && npm start
```

## Migrations

```bash
python -m alembic upgrade head
```

## GitHub Actions

`.github/workflows/ci.yml` installs deps, runs pytest (mocked providers), and
builds the Next.js app. **Deploy jobs are gated** until repository secrets for
Vercel/Render (or equivalent) are configured.

## Monitoring

- Sentry: set `SENTRY_DSN` (no-op stub when absent)
- PostHog: set `POSTHOG_API_KEY` (mock when absent)
- Prefer structured logs + `provider_usage` / `audit_logs` tables

## Environment variables

Copy from [`.env.example`](../.env.example) for each environment. Never commit real secrets.

**Required:** `DATABASE_URL`, `REDIS_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
`SUPABASE_SERVICE_ROLE_KEY`, `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_BASE_URL`, `CORS_ALLOW_ORIGINS`.

**Production discovery (QStash):** `TASK_BACKEND=qstash`, `QSTASH_TOKEN`,
`QSTASH_CURRENT_SIGNING_KEY`, `QSTASH_CALLBACK_BASE_URL` (public API HTTPS origin,
no trailing slash).

**Providers (as needed):** `LLM_PROVIDER` + keys, `TAVILY_API_KEY`,
`FIRECRAWL_*`, `RESEND_*`, `SUPABASE_STORAGE_BUCKET`.

## Backup and recovery

- **Postgres** is the system of record — enable provider backups / PITR; test restore periodically.
- **Redis** is ephemeral (queues/cache/SSE); a fresh instance is fine after restore.
- **Object storage** — enable versioning/soft-delete for resumes; regenerate signed URLs after recovery.
- After Postgres restore: confirm `vector` extension, redeploy API + web, re-check QStash schedules.
