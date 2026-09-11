"""add_embedding_columns

Revision ID: g7d0e3b82c41
Revises: a1b2c3d4e5f6
Create Date: 2026-09-11 17:15:00.000000

Adds pgvector embedding storage on jobs, user_profiles, company_research,
and resume_versions. Does not invent new entity tables.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "g7d0e3b82c41"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    for table in ("jobs", "user_profiles", "company_research", "resume_versions"):
        op.add_column(table, sa.Column("embedding", Vector(_DIM), nullable=True))
        op.add_column(table, sa.Column("embedding_model", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("embedding_version", sa.Text(), nullable=True))
        op.add_column(
            table,
            sa.Column("embedding_generated_at", sa.DateTime(timezone=True), nullable=True),
        )

    op.add_column(
        "resume_versions",
        sa.Column("section_embeddings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "job_matches",
        sa.Column("scoring_algorithm_version", sa.Text(), nullable=True),
    )
    op.add_column(
        "job_matches",
        sa.Column("semantic_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("job_matches", "semantic_score")
    op.drop_column("job_matches", "scoring_algorithm_version")
    op.drop_column("resume_versions", "section_embeddings")
    for table in ("resume_versions", "company_research", "user_profiles", "jobs"):
        op.drop_column(table, "embedding_generated_at")
        op.drop_column(table, "embedding_version")
        op.drop_column(table, "embedding_model")
        op.drop_column(table, "embedding")
