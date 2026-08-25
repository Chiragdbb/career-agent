"""add_resume_version_parser_version

Revision ID: d4a7c2e81f09
Revises: c3f8a1b92d04
Create Date: 2026-08-25 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4a7c2e81f09"
down_revision: Union[str, Sequence[str], None] = "c3f8a1b92d04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("resume_versions", sa.Column("parser_version", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("resume_versions", "parser_version")
