"""workflow_progress_events

Revision ID: i9f2a5d04e63
Revises: h8e1f4c93d52
Create Date: 2026-09-23 01:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i9f2a5d04e63"
down_revision: Union[str, Sequence[str], None] = "h8e1f4c93d52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_progress_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workflow_type", sa.Text(), nullable=False),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False, server_default="working"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("display", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_workflow_progress_events_user_id",
        "workflow_progress_events",
        ["user_id"],
    )
    op.create_index(
        "ix_workflow_progress_events_workflow_run_id",
        "workflow_progress_events",
        ["workflow_run_id"],
    )
    op.create_index(
        "ix_workflow_progress_events_run_created",
        "workflow_progress_events",
        ["workflow_run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_progress_events_run_created",
        table_name="workflow_progress_events",
    )
    op.drop_index(
        "ix_workflow_progress_events_workflow_run_id",
        table_name="workflow_progress_events",
    )
    op.drop_index(
        "ix_workflow_progress_events_user_id",
        table_name="workflow_progress_events",
    )
    op.drop_table("workflow_progress_events")
