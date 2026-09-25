# AI Career Agent

An AI-assisted system for discovering jobs, researching companies, tailoring resumes, managing applications, coordinating outreach, and tracking the full hiring pipeline — with human oversight and auditability built in.

## What It Does

- **Discovery** — Find and ingest job postings from configured sources.
- **Research** — Gather company context to inform applications and outreach.
- **Documents** — Manage resumes, versions, and supporting materials without fabricating experience.
- **Applications** — Track application lifecycle from draft through submission with evidence.
- **Outreach** — Draft and send communications only with explicit user approval (or automation rules).
- **Pipeline** — Monitor interviews, offers, notifications, and tasks requiring human action.

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│  apps/web   │     │  apps/api   │     │   MCP server     │
│  (UI)       │────▶│  (HTTP)     │     │  (tool surface)  │
└─────────────┘     └──────┬──────┘     └────────┬─────────┘
                           │                      │
                           ▼                      ▼
                    ┌──────────────────────────────────┐
                    │   packages/domain (business logic) │
                    └──────────────────┬───────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                        ▼
     ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
     │ packages/       │    │ packages/       │    │ workers/        │
     │ providers       │    │ prompts         │    │ (async jobs)    │
     └────────┬────────┘    └─────────────────┘    └────────┬────────┘
              │                                               │
              ▼                                               ▼
     ┌─────────────────┐                            ┌─────────────────┐
     │ External APIs   │                            │ Redis (queues)  │
     │ (via providers) │                            └─────────────────┘
     └─────────────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │   PostgreSQL    │
                              │ (system of record)│
                              └─────────────────┘
```

**Default provider targets** (swappable behind interfaces in `packages/providers/`):

| Capability | Interface | Default target |
|------------|-----------|----------------|
| Auth | AuthProvider | Supabase Auth |
| LLM / structured extraction | LLMProvider | Groq or Gemini |
| Object storage | StorageProvider | Supabase Storage |
| Web scraping | ScraperProvider | Self-hosted Firecrawl |
| Web search | SearchProvider | Tavily |
| Outbound email | EmailSenderProvider | Resend |

**Key principles:**

- **PostgreSQL** stores all durable state (see `database/models/schema.py` + Alembic migrations).
- **Redis** backs job queues and caching.
- **Workers** handle long-running or scheduled tasks (discovery, research, outreach, etc.).
- **Provider adapters** isolate third-party SDKs behind interfaces — vendors above are defaults, not hard-wired architecture.
- **Tenant isolation** — every user-owned row is scoped to a user/tenant.
- **MCP tools** expose capabilities to AI assistants but delegate to domain services.

## Repository Structure

```
career-agent/
├── apps/
│   ├── web/              # Frontend UI
│   └── api/              # HTTP API (FastAPI)
├── packages/
│   ├── domain/           # Business logic and domain services
│   ├── providers/        # Third-party provider adapters
│   ├── prompts/          # LLM prompt templates
│   └── shared/           # Shared utilities and types
├── workers/
│   ├── discovery/        # Job discovery and ingestion
│   ├── research/         # Company research jobs
│   ├── contacts/         # Contact enrichment
│   ├── documents/        # Resume/document generation
│   ├── applications/     # Application submission workflows
│   ├── outreach/         # Email/messaging workflows
│   └── notifications/    # Notification delivery
├── mcp/                  # MCP server exposing tools to AI assistants
├── database/
│   ├── migrations/       # Schema migrations
│   └── models/           # SQLAlchemy models
├── tests/                # Test suite
├── docker/               # Docker Compose and container config
├── docs/
│   ├── local-development.md
│   └── deployment.md
├── AGENTS.md             # Mandatory development rules
└── README.md
```

## Getting Started

1. Copy environment variables:

   ```bash
   cp .env.example .env
   ```

2. Follow [docs/local-development.md](./docs/local-development.md) for Docker Postgres/Redis and running the API + web app.

3. Fill in required keys from `.env.example` (Supabase Auth + Storage, LLM, Firecrawl, Tavily, Resend as needed).

4. Read [AGENTS.md](./AGENTS.md) before making changes — it defines mandatory development rules for humans and AI agents.

5. Production deploy: [docs/deployment.md](./docs/deployment.md).

## Development Rules

All contributors (human and AI) must follow the rules in **[AGENTS.md](./AGENTS.md)**. Highlights:

- Business logic lives in `packages/domain/`, not in route handlers or MCP tools.
- Never fabricate candidate data or invent email addresses.
- Never mark an application as submitted without evidence.
- External communication requires user approval unless an automation rule explicitly allows it.
- Database changes go through migrations; critical logic needs tests.

## Status

Foundation through SaaS dashboard is in place. Recent productization work includes
pgvector hybrid matching, automation rules, provider quotas, security hardening,
MCP domain-service tools, scheduled discovery, E2E vertical-slice tests, and
deployment/CI docs. Production cloud deploy still requires human-provided secrets
(see `docs/deployment.md`).
