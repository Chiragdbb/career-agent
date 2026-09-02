"""discovery_fixes_schema

Revision ID: a1b2c3d4e5f6
Revises: f6c9e2a71b30
Create Date: 2026-09-02 15:15:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f6c9e2a71b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE workflow_run_status ADD VALUE IF NOT EXISTS 'cancelling'")

    op.add_column(
        "jobs",
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "discovery_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_jobs_discovery_run_id", "jobs", ["discovery_run_id"])

    op.add_column(
        "job_matches",
        sa.Column("skill_alignment", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.execute(
        "UPDATE jobs SET last_scraped_at = updated_at WHERE last_scraped_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("job_matches", "skill_alignment")
    op.drop_index("ix_jobs_discovery_run_id", table_name="jobs")
    op.drop_column("jobs", "discovery_run_id")
    op.drop_column("jobs", "last_scraped_at")
    # PostgreSQL does not support removing enum values; leave 'cancelling' in place.
