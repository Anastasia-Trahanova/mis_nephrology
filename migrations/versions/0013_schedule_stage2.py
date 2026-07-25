"""Поля отмены записи расписания.

Revision ID: 0013_schedule_stage2
Revises: 0012_schedule_rebuild_stage1
Create Date: 2026-07-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013_schedule_stage2"
down_revision = "0012_schedule_rebuild_stage1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schedule_entries", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.add_column(
        "schedule_entries",
        sa.Column(
            "cancelled_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("schedule_entries", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.create_index("ix_schedule_entries_status", "schedule_entries", ["status"])


def downgrade() -> None:
    op.drop_index("ix_schedule_entries_status", table_name="schedule_entries")
    op.drop_column("schedule_entries", "cancel_reason")
    op.drop_column("schedule_entries", "cancelled_by_user_id")
    op.drop_column("schedule_entries", "cancelled_at")
