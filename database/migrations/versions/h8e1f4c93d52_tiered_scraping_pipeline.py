"""tiered_scraping_pipeline

Revision ID: h8e1f4c93d52
Revises: g7d0e3b82c41
Create Date: 2026-09-19 13:40:00.000000

Adds job scrape metadata columns, contact cache freshness fields,
and provider_usage entity/metric extensions for the tiered scraping pipeline.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "h8e1f4c93d52"
down_revision: Union[str, Sequence[str], None] = "g7d0e3b82c41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- jobs: structured scrape fields (external_id already exists) ---
    op.add_column("jobs", sa.Column("source", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("company_domain", sa.Text(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("skills", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.add_column("jobs", sa.Column("remote_type", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("employment_type", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("seniority", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("salary_min", sa.Numeric(), nullable=True))
    op.add_column("jobs", sa.Column("salary_max", sa.Numeric(), nullable=True))
    op.add_column("jobs", sa.Column("salary_currency", sa.Text(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        UPDATE jobs
        SET scraped_at = COALESCE(last_scraped_at, updated_at, created_at)
        WHERE scraped_at IS NULL
        """
    )

    # Prefer (external_id, company_domain) dedup over global external_id uniqueness.
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS uq_jobs_external_id")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS jobs_external_dedup
        ON jobs (external_id, company_domain)
        WHERE external_id IS NOT NULL
        """
    )
    op.create_index("ix_jobs_source", "jobs", ["source"])
    op.create_index("ix_jobs_company_domain", "jobs", ["company_domain"])

    # --- contacts: source / confidence / freshness ---
    op.add_column("contacts", sa.Column("source", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("confidence", sa.Text(), nullable=True))
    op.add_column(
        "contacts",
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_contacts_company_source", "contacts", ["company_id", "source"])

    # --- provider_usage: related entity + finer metrics ---
    op.alter_column(
        "provider_usage",
        "user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.add_column("provider_usage", sa.Column("related_entity_type", sa.Text(), nullable=True))
    op.add_column(
        "provider_usage",
        sa.Column("related_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("provider_usage", sa.Column("tokens_input", sa.Integer(), nullable=True))
    op.add_column("provider_usage", sa.Column("tokens_output", sa.Integer(), nullable=True))
    op.add_column(
        "provider_usage",
        sa.Column("requests_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("provider_usage", sa.Column("error_code", sa.Text(), nullable=True))
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS provider_usage_provider_day
        ON provider_usage (provider_name, created_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS provider_usage_provider_day")
    op.drop_column("provider_usage", "error_code")
    op.drop_column("provider_usage", "requests_count")
    op.drop_column("provider_usage", "tokens_output")
    op.drop_column("provider_usage", "tokens_input")
    op.drop_column("provider_usage", "related_entity_id")
    op.drop_column("provider_usage", "related_entity_type")
    op.alter_column(
        "provider_usage",
        "user_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

    op.drop_index("ix_contacts_company_source", table_name="contacts")
    op.drop_column("contacts", "last_verified_at")
    op.drop_column("contacts", "confidence")
    op.drop_column("contacts", "source")

    op.drop_index("ix_jobs_company_domain", table_name="jobs")
    op.drop_index("ix_jobs_source", table_name="jobs")
    op.execute("DROP INDEX IF EXISTS jobs_external_dedup")
    op.create_unique_constraint("uq_jobs_external_id", "jobs", ["external_id"])
    op.drop_column("jobs", "scraped_at")
    op.drop_column("jobs", "salary_currency")
    op.drop_column("jobs", "salary_max")
    op.drop_column("jobs", "salary_min")
    op.drop_column("jobs", "seniority")
    op.drop_column("jobs", "employment_type")
    op.drop_column("jobs", "remote_type")
    op.drop_column("jobs", "skills")
    op.drop_column("jobs", "company_domain")
    op.drop_column("jobs", "source")
