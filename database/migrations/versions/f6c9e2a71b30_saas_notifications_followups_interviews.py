"""saas_notifications_followups_interviews

Revision ID: f6c9e2a71b30
Revises: e5b8d3f92a10
Create Date: 2026-08-25 17:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6c9e2a71b30"
down_revision: Union[str, Sequence[str], None] = "e5b8d3f92a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

follow_up_status = sa.Enum(
    "scheduled",
    "pending_approval",
    "sent",
    "cancelled",
    "completed",
    name="follow_up_status",
)


def upgrade() -> None:
    op.add_column("notifications", sa.Column("dedupe_key", sa.Text(), nullable=True))
    op.create_index(
        "ix_notifications_user_dedupe_key",
        "notifications",
        ["user_id", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )

    op.add_column("interviews", sa.Column("round", sa.Integer(), nullable=True))
    op.add_column("interviews", sa.Column("format", sa.Text(), nullable=True))
    op.add_column("interviews", sa.Column("interviewer", sa.Text(), nullable=True))

    follow_up_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "follow_ups",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=True),
        sa.Column("outreach_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "scheduled",
                "pending_approval",
                "sent",
                "cancelled",
                "completed",
                name="follow_up_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("cancelled_reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outreach_id"], ["outreach.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_follow_ups_user_dedupe"),
    )
    op.create_index(op.f("ix_follow_ups_user_id"), "follow_ups", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_follow_ups_application_id"), "follow_ups", ["application_id"], unique=False
    )
    op.create_index(
        op.f("ix_follow_ups_outreach_id"), "follow_ups", ["outreach_id"], unique=False
    )
    op.create_index(
        op.f("ix_follow_ups_next_action_at"), "follow_ups", ["next_action_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_follow_ups_next_action_at"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_outreach_id"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_application_id"), table_name="follow_ups")
    op.drop_index(op.f("ix_follow_ups_user_id"), table_name="follow_ups")
    op.drop_table("follow_ups")
    follow_up_status.drop(op.get_bind(), checkfirst=True)

    op.drop_column("interviews", "interviewer")
    op.drop_column("interviews", "format")
    op.drop_column("interviews", "round")

    op.drop_index("ix_notifications_user_dedupe_key", table_name="notifications")
    op.drop_column("notifications", "dedupe_key")
