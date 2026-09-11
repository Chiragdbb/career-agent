# Production Deployment

This document describes how to deploy Career Agent. **Deploy credentials / cloud
accounts are HUMAN INPUT** — CI and docs are provided; live deploy is not
automated until secrets exist.

## Recommended topology

| Component | Suggested host | Notes |
|-----------|----------------|-------|
| Frontend (`apps/web`) | Vercel | Next.js; set `NEXT_PUBLIC_*` |
| API (`apps/api`) | Render / Fly / AWS | Bind `0.0.0.0:$PORT` |
| Workers (Celery) | Render / Fly / AWS | Same image as API + worker command |
| Celery beat | Same as workers | Scheduled discovery |
| PostgreSQL + pgvector | Managed Postgres | Enable `vector` extension |
| Redis | Managed Redis | Queues + SSE pub/sub |
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

Beat (scheduled discovery):

```bash
export PYTHONPATH=".:apps/api"
celery -A workers.celery_app.celery_app beat --loglevel=info
```

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
