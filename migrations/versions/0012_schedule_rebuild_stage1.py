"""Перестройка таблиц расписания под записи произвольной длительности.

Revision ID: 0012_schedule_rebuild_stage1
Revises: 0011_history_studies_fields
Create Date: 2026-07-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012_schedule_rebuild_stage1"
down_revision = "0011_history_studies_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Старый MVP создавал заранее фиксированные слоты. Новый модуль хранит только
    # реальные записи с произвольным началом и окончанием.
    op.execute("DROP TABLE IF EXISTS schedule_bookings CASCADE")
    op.execute("DROP TABLE IF EXISTS schedule_slots CASCADE")

    op.create_table(
        "schedule_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "scheduled_doctor_id",
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
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("appointment_type", sa.String(length=20), nullable=False, server_default="primary"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="booked"),
        sa.Column(
            "actual_doctor_id",
            sa.Integer(),
            sa.ForeignKey("doctors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "appointment_id",
            sa.Integer(),
            sa.ForeignKey("appointments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("ends_at > starts_at", name="ck_schedule_entries_time"),
        sa.CheckConstraint(
            "appointment_type IN ('primary', 'repeat')",
            name="ck_schedule_entries_appointment_type",
        ),
        sa.CheckConstraint(
            "status IN ('booked', 'arrived', 'no_show', 'cancelled')",
            name="ck_schedule_entries_status",
        ),
    )
    op.create_index(
        "ix_schedule_entries_doctor_period",
        "schedule_entries",
        ["scheduled_doctor_id", "starts_at", "ends_at"],
    )
    op.create_index(
        "ix_schedule_entries_location_period",
        "schedule_entries",
        ["location_id", "starts_at", "ends_at"],
    )
    op.create_index("ix_schedule_entries_patient", "schedule_entries", ["patient_id"])
    op.create_index(
        "ux_schedule_entries_appointment",
        "schedule_entries",
        ["appointment_id"],
        unique=True,
        postgresql_where=sa.text("appointment_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_schedule_entries_appointment", table_name="schedule_entries")
    op.drop_index("ix_schedule_entries_patient", table_name="schedule_entries")
    op.drop_index("ix_schedule_entries_location_period", table_name="schedule_entries")
    op.drop_index("ix_schedule_entries_doctor_period", table_name="schedule_entries")
    op.drop_table("schedule_entries")

    op.create_table(
        "schedule_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("slot_kind", sa.String(length=20), nullable=False, server_default="primary"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="free"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("ends_at > starts_at", name="ck_schedule_slots_time"),
        sa.CheckConstraint("slot_kind IN ('primary', 'repeat')", name="ck_schedule_slots_kind"),
        sa.CheckConstraint(
            "status IN ('free', 'booked', 'blocked', 'cancelled', 'completed', 'no_show')",
            name="ck_schedule_slots_status",
        ),
    )
    op.create_table(
        "schedule_bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slot_id", sa.Integer(), sa.ForeignKey("schedule_slots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="booked"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("booked_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("booked_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("cancelled_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "status IN ('booked', 'cancelled', 'completed', 'no_show')",
            name="ck_schedule_bookings_status",
        ),
    )
    op.create_index("ux_schedule_slots_doctor_time", "schedule_slots", ["doctor_id", "starts_at", "ends_at"], unique=True)
    op.create_index(
        "ux_schedule_bookings_active_slot",
        "schedule_bookings",
        ["slot_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('booked', 'completed', 'no_show')"),
    )
    op.create_index("ix_schedule_slots_doctor_period", "schedule_slots", ["doctor_id", "starts_at", "ends_at"])
    op.create_index("ix_schedule_slots_location_period", "schedule_slots", ["location_id", "starts_at", "ends_at"])
    op.create_index("ix_schedule_bookings_slot", "schedule_bookings", ["slot_id"])
    op.create_index("ix_schedule_bookings_patient", "schedule_bookings", ["patient_id"])
    op.create_index("ix_schedule_bookings_status", "schedule_bookings", ["status"])
