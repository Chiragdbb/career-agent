# Backup and Recovery

## PostgreSQL (system of record)

- Enable automated daily backups on the managed provider (PITR if available).
- Retain at least 7–30 days depending on compliance needs.
- Test restore quarterly into a non-production instance.
- After restore: run `python -m alembic upgrade head` only if the backup predates pending migrations; otherwise leave schema as restored.

## Redis

- Redis is **ephemeral** for queues/cache/SSE. Loss is acceptable; in-flight Celery tasks may need re-queue.
- Do not store durable tenant data solely in Redis.

## Object storage

- Supabase Storage / S3-compatible buckets should have versioning or soft-delete enabled for resumes/documents.
- Signed URLs expire; regenerate via the API after recovery.

## Secrets

- Keep secrets in the host secret manager; rotate after any incident.
- Document who can access production credentials (HUMAN INPUT / ops process).

## Application state recovery checklist

1. Restore Postgres from snapshot
2. Verify `vector` extension exists
3. Confirm Redis connectivity (fresh empty instance OK)
4. Redeploy API + workers + beat + web
5. Smoke: `/api/v1/health`, auth `/me`, upload resume, list jobs
6. Re-run failed Celery tasks if needed via admin tooling
