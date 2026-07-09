"""create admin schedule MVP

Revision ID: 0008_schedule_admin_mvp
Revises: 0007_audit_event_changes
Create Date: 2026-07-09

Назначение миграции:
- добавляет минимальный модуль расписания для администратора;
- создаёт слоты расписания врачей;
- создаёт записи пациентов на слоты;
- не изменяет medical appointments: appointments остаётся фактом медицинского приёма.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_schedule_admin_mvp"
down_revision = "0007_audit_event_changes"
branch_labels = None
depends_on = None


SLOT_KIND_VALUES = ("primary", "repeat")
SLOT_STATUS_VALUES = ("free", "booked", "blocked", "cancelled", "completed", "no_show")
BOOKING_STATUS_VALUES = ("booked", "cancelled", "completed", "no_show")


def upgrade() -> None:
    """Создаёт таблицы расписания и индексы защиты от двойной записи."""
    op.create_table(
        "schedule_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "doctor_id",
            sa.Integer(),
            sa.ForeignKey("doctors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("slot_kind", sa.String(length=20), nullable=False, server_default="primary"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="free"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_schedule_slots_time"),
        sa.CheckConstraint(
            "slot_kind IN ('primary', 'repeat')",
            name="ck_schedule_slots_kind",
        ),
        sa.CheckConstraint(
            "status IN ('free', 'booked', 'blocked', 'cancelled', 'completed', 'no_show')",
            name="ck_schedule_slots_status",
        ),
    )

    op.create_table(
        "schedule_bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "slot_id",
            sa.Integer(),
            sa.ForeignKey("schedule_slots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="booked"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "booked_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "booked_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "cancelled_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column(
            "appointment_id",
            sa.Integer(),
            sa.ForeignKey("appointments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('booked', 'cancelled', 'completed', 'no_show')",
            name="ck_schedule_bookings_status",
        ),
    )

    op.create_index(
        "ux_schedule_slots_doctor_time",
        "schedule_slots",
        ["doctor_id", "starts_at", "ends_at"],
        unique=True,
    )
    op.create_index(
        "ux_schedule_bookings_active_slot",
        "schedule_bookings",
        ["slot_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('booked', 'completed', 'no_show')"),
    )
    op.create_index(
        "ix_schedule_slots_doctor_period",
        "schedule_slots",
        ["doctor_id", "starts_at", "ends_at"],
    )
    op.create_index(
        "ix_schedule_slots_location_period",
        "schedule_slots",
        ["location_id", "starts_at", "ends_at"],
    )
    op.create_index("ix_schedule_bookings_slot", "schedule_bookings", ["slot_id"])
    op.create_index("ix_schedule_bookings_patient", "schedule_bookings", ["patient_id"])
    op.create_index("ix_schedule_bookings_status", "schedule_bookings", ["status"])


def downgrade() -> None:
    """Удаляет таблицы расписания."""
    op.drop_index("ix_schedule_bookings_status", table_name="schedule_bookings")
    op.drop_index("ix_schedule_bookings_patient", table_name="schedule_bookings")
    op.drop_index("ix_schedule_bookings_slot", table_name="schedule_bookings")
    op.drop_index("ix_schedule_slots_location_period", table_name="schedule_slots")
    op.drop_index("ix_schedule_slots_doctor_period", table_name="schedule_slots")
    op.drop_index("ux_schedule_bookings_active_slot", table_name="schedule_bookings")
    op.drop_index("ux_schedule_slots_doctor_time", table_name="schedule_slots")
    op.drop_table("schedule_bookings")
    op.drop_table("schedule_slots")
