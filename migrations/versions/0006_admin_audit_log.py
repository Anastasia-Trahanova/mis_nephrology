"""create admin audit log

Revision ID: 0006_admin_audit
Revises: 0005_demo_icd10_seed
Create Date: 2026-07-09

Назначение миграции:
- создаёт таблицу audit_events для журнала действий пользователей;
- журнал нужен странице администратора /admin/audit;
- таблица хранит только безопасные служебные факты: кто, когда, какое действие выполнил,
  с каким patient_id/appointment_id и чем закончился запрос.

Что редактировать здесь:
- только схему audit_events, если меняется состав журналируемых полей.

Что не редактировать здесь:
- демо-данные;
- пароли пользователей;
- медицинские таблицы пациентов и приёмов.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_admin_audit"
down_revision = "0005_demo_icd10_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_login", sa.Text(), nullable=True),
        sa.Column("user_role", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("result", sa.String(length=30), nullable=False, server_default="success"),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint("result IN ('success', 'error', 'denied')", name="ck_audit_events_result"),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_result", "audit_events", ["result"])
    op.create_index("ix_audit_events_patient_id", "audit_events", ["patient_id"])
    op.create_index("ix_audit_events_appointment_id", "audit_events", ["appointment_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_appointment_id", table_name="audit_events")
    op.drop_index("ix_audit_events_patient_id", table_name="audit_events")
    op.drop_index("ix_audit_events_result", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_table("audit_events")
