# Production Environment Variables

Copy from `.env.example` and fill for each environment. Never commit real secrets.

## Required

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres (pgvector-enabled) |
| `REDIS_URL` | Celery + cache + SSE |
| `SUPABASE_URL` | Auth JWKS + Storage |
| `SUPABASE_ANON_KEY` | Public (web) |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only storage/admin |
| `NEXT_PUBLIC_SUPABASE_URL` | Web auth |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Web auth |
| `NEXT_PUBLIC_API_BASE_URL` | Web → API |
| `CORS_ALLOW_ORIGINS` | Allowed browser origins |

## Strongly recommended

| Variable | Purpose |
|----------|---------|
| `LLM_PROVIDER` + `GROQ_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY` | LLM |
| `TAVILY_API_KEY` | Search |
| `FIRECRAWL_BASE_URL` / `FIRECRAWL_API_KEY` | Scrape |
| `RESEND_API_KEY` + `RESEND_FROM_EMAIL` | Outbound email |
| `SUPABASE_STORAGE_BUCKET` | Resume/docs bucket |

## Optional

| Variable | Purpose |
|----------|---------|
| `EMBEDDING_API_KEY` / `EMBEDDING_MODEL` / `EMBEDDING_BASE_URL` | Semantic matching (else mock) |
| `SENTRY_DSN` | Error tracking (stub if unset) |
| `POSTHOG_API_KEY` / `POSTHOG_HOST` | Product analytics (mock if unset) |
| `NOTION_API_KEY` / `NOTION_DATABASE_ID` | Optional export only |
| `MCP_USER_ID` / `MCP_AUTH_SUBJECT` / `MCP_AUTH_TOKEN` | MCP tenant context |
| `APOLLO_API_KEY` / `HUNTER_API_KEY` | People/email enrichment |

## Security notes

- Do not set `SUPABASE_SERVICE_ROLE_KEY` in `NEXT_PUBLIC_*`
- Prefer private storage + signed URLs
- Rotate provider keys on schedule; restrict outbound egress where possible
