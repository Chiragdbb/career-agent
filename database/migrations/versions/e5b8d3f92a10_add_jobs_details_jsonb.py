"""add_jobs_details_jsonb

Revision ID: e5b8d3f92a10
Revises: d4a7c2e81f09
Create Date: 2026-08-25 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e5b8d3f92a10"
down_revision: Union[str, Sequence[str], None] = "d4a7c2e81f09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "details")
