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

See [production-environment.md](./production-environment.md) for the env var checklist.

## Build & run (containers)

API example:

```bash
pip install -r requirements.txt
export PYTHONPATH=".:apps/api"
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir apps/api
```

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
