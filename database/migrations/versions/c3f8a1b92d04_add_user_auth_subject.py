"""add_user_auth_subject

Revision ID: c3f8a1b92d04
Revises: ae9b41ee8363
Create Date: 2026-08-24 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3f8a1b92d04"
down_revision: Union[str, Sequence[str], None] = "ae9b41ee8363"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth_subject", sa.Text(), nullable=True))
    # Local/dev DBs should be empty; backfill a deterministic subject if any rows exist.
    op.execute(
        "UPDATE users SET auth_subject = 'migrated-' || id::text "
        "WHERE auth_subject IS NULL"
    )
    op.alter_column("users", "auth_subject", nullable=False)
    op.create_index(op.f("ix_users_auth_subject"), "users", ["auth_subject"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_auth_subject"), table_name="users")
    op.drop_column("users", "auth_subject")
