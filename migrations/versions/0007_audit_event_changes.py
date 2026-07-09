"""
Создать таблицу подробностей событий аудита.

Назначение миграции:
- добавить audit_event_changes для детального журнала медицинских изменений;
- оставить audit_events как основную строку события;
- связать подробности с основным событием через audit_event_id;
- при удалении события аудита удалять его подробности каскадом.

Что редактировать здесь:
- только структуру audit_event_changes, если меняется модель аудита.

Что не редактировать здесь:
- тексты событий и правила формирования изменений;
- HTML административной страницы;
- ролевые права.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_audit_event_changes"
down_revision = "0006_admin_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавляет таблицу детальных изменений аудита."""
    op.create_table(
        "audit_event_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "audit_event_id",
            sa.Integer(),
            sa.ForeignKey("audit_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section", sa.String(length=100), nullable=False),
        sa.Column("section_label", sa.String(length=255), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=True),
        sa.Column("field_label", sa.String(length=255), nullable=True),
        sa.Column("change_type", sa.String(length=60), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_audit_event_changes_event_id",
        "audit_event_changes",
        ["audit_event_id"],
    )
    op.create_index(
        "ix_audit_event_changes_section",
        "audit_event_changes",
        ["section"],
    )
    op.create_index(
        "ix_audit_event_changes_type",
        "audit_event_changes",
        ["change_type"],
    )


def downgrade() -> None:
    """Удаляет таблицу детальных изменений аудита."""
    op.drop_index("ix_audit_event_changes_type", table_name="audit_event_changes")
    op.drop_index("ix_audit_event_changes_section", table_name="audit_event_changes")
    op.drop_index("ix_audit_event_changes_event_id", table_name="audit_event_changes")
    op.drop_table("audit_event_changes")
