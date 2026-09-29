"""spec_pipeline_extensions

Revision ID: j9k2l3m4n5o6
Revises: i9f2a5d04e63
Create Date: 2026-09-29 12:00:00.000000

Jobs completeness/provenance, contact tier, resume ATS/render, provider_usage tier.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "j9k2l3m4n5o6"
down_revision: Union[str, Sequence[str], None] = "i9f2a5d04e63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("completeness_score", sa.Integer(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("missing_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("jobs", sa.Column("extraction_provenance", sa.Text(), nullable=True))
    op.create_index("ix_jobs_completeness_score", "jobs", ["completeness_score"])

    op.add_column("contacts", sa.Column("tier_reached", sa.Integer(), nullable=True))

    op.add_column("resume_versions", sa.Column("render_engine", sa.Text(), nullable=True))
    op.add_column("resume_versions", sa.Column("html_path", sa.Text(), nullable=True))
    op.add_column("resume_versions", sa.Column("ats_score", sa.Integer(), nullable=True))
    op.add_column(
        "resume_versions",
        sa.Column("ats_issues", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "resume_versions",
        sa.Column("ats_checked_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column("provider_usage", sa.Column("tier_reached", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("provider_usage", "tier_reached")
    op.drop_column("resume_versions", "ats_checked_at")
    op.drop_column("resume_versions", "ats_issues")
    op.drop_column("resume_versions", "ats_score")
    op.drop_column("resume_versions", "html_path")
    op.drop_column("resume_versions", "render_engine")
    op.drop_column("contacts", "tier_reached")
    op.drop_index("ix_jobs_completeness_score", table_name="jobs")
    op.drop_column("jobs", "extraction_provenance")
    op.drop_column("jobs", "missing_fields")
    op.drop_column("jobs", "completeness_score")
