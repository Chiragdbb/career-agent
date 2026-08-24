# Local Development Infrastructure

Local Postgres (with **pgvector**) and Redis via Docker Compose. API, workers, and frontend containers are not included yet.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
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
| `DATABASE_URL` | `postgresql://career:career@localhost:5432/career_agent` | App DB URL |
| `REDIS_URL` | `redis://localhost:6379/0` | App Redis URL |

## Start

From the **repository root**:

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d
```

Check containers:

```bash
docker ps
docker compose --env-file .env -f docker/docker-compose.yml ps
```

Healthy services should show `career-agent-db` (Postgres/pgvector on port **5432**) and `career-agent-redis` (Redis on port **6379**).

## Stop

Stop containers (keep data volumes):

```bash
docker compose --env-file .env -f docker/docker-compose.yml down
```

Stop and **delete volumes** (wipes local Postgres/Redis data):

```bash
docker compose --env-file .env -f docker/docker-compose.yml down -v
```

## Optional: self-hosted Firecrawl

Core Compose only runs Postgres and Redis. For scraping, run Firecrawl separately (or use an existing instance) and point the app at it:

```bash
# In .env — ScraperProvider talks to your instance via FIRECRAWL_BASE_URL
FIRECRAWL_BASE_URL=http://localhost:3002
# FIRECRAWL_API_KEY=   # only if your instance requires one
```

Do not assume the paid Firecrawl cloud API. Adapter code should use the same `ScraperProvider` interface regardless of where Firecrawl is hosted. A Firecrawl service is intentionally **not** part of `docker/docker-compose.yml` yet.

## Notes

- Passwords in `.env` / `.env.example` are for **local development only**. Do not reuse them in production.
- If you previously ran an older Compose file with a different `POSTGRES_USER`, recreate volumes with `down -v` before starting again so init scripts apply the new role/database.
- Enable the `vector` extension in a later migrations step (`CREATE EXTENSION IF NOT EXISTS vector;`) — the image includes pgvector but does not create the extension automatically.
- Auth (Supabase), LLM (Groq/Gemini), and storage (Supabase Storage) keys live in `.env.example`; for private storage buckets, object reads should use signed URLs generated server-side (so `SUPABASE_JWT_SECRET` is not needed for that assumption). `SUPABASE_STORAGE_PUBLIC_URL` is optional and only relevant for public buckets. Adapters are not wired yet — see README provider table.
