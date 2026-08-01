"""Локальный регистр ХБП и управленческие врачебные роли.

Revision ID: 0014_ckd_registry_roles
Revises: 0013_schedule_stage2
Create Date: 2026-08-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0014_ckd_registry_roles"
down_revision = "0013_schedule_stage2"
branch_labels = None
depends_on = None

ROLE_CHECK = """
role IN ('admin', 'doctor', 'chief_physician', 'department_head', 'patient')
AND (
    (role = 'admin' AND doctor_id IS NULL AND patient_id IS NULL)
    OR
    (role IN ('doctor', 'chief_physician', 'department_head')
        AND doctor_id IS NOT NULL AND patient_id IS NULL)
    OR
    (role = 'patient' AND doctor_id IS NULL AND patient_id IS NOT NULL)
)
"""

OLD_ROLE_CHECK = """
role IN ('admin', 'doctor', 'patient')
AND (
    (role = 'admin' AND doctor_id IS NULL AND patient_id IS NULL)
    OR
    (role = 'doctor' AND doctor_id IS NOT NULL AND patient_id IS NULL)
    OR
    (role = 'patient' AND doctor_id IS NULL AND patient_id IS NOT NULL)
)
"""

OUTCOME_VALUES = (
    "rrt_hemodialysis",
    "rrt_peritoneal_dialysis",
    "rrt_kidney_transplant",
    "death",
)


def upgrade() -> None:
    # Сначала расширяем допустимые роли, затем назначаем их пользователям.
    op.drop_constraint("chk_users_role_model", "users", type_="check")
    op.create_check_constraint("chk_users_role_model", "users", ROLE_CHECK)

    op.execute(
        sa.text("UPDATE users SET role = 'chief_physician' WHERE login = 'lobanova_n'")
    )
    op.execute(
        sa.text("UPDATE users SET role = 'department_head' WHERE login = 'vozova_a'")
    )

    op.create_table(
        "ckd_registry_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("included_at", sa.Date(), nullable=False),
        sa.Column(
            "included_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("diagnosis_at_inclusion", sa.Text(), nullable=False),
        sa.Column("egfr_at_inclusion", sa.Numeric(6, 2), nullable=True),
        sa.Column("ckd_stage_at_inclusion", sa.String(length=3), nullable=True),
        sa.Column("comment_at_inclusion", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("closed_at", sa.Date(), nullable=True),
        sa.Column(
            "closed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "egfr_at_inclusion IS NULL OR egfr_at_inclusion >= 0",
            name="ck_ckd_registry_entries_egfr_non_negative",
        ),
        sa.CheckConstraint(
            "ckd_stage_at_inclusion IS NULL OR "
            "ckd_stage_at_inclusion IN ('С1', 'С2', 'С3а', 'С3б', 'С4', 'С5')",
            name="ck_ckd_registry_entries_stage",
        ),
        sa.CheckConstraint(
            "(is_active AND closed_at IS NULL) OR "
            "(NOT is_active AND closed_at IS NOT NULL AND close_reason IS NOT NULL)",
            name="ck_ckd_registry_entries_closure",
        ),
        sa.UniqueConstraint("patient_id", name="uq_ckd_registry_entries_patient"),
    )
    op.create_index(
        "ix_ckd_registry_entries_included_at",
        "ckd_registry_entries",
        ["included_at"],
    )
    op.create_index(
        "ix_ckd_registry_entries_is_active",
        "ckd_registry_entries",
        ["is_active"],
    )

    op.create_table(
        "ckd_registry_outcomes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "registry_entry_id",
            sa.BigInteger(),
            sa.ForeignKey("ckd_registry_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("outcome_type", sa.String(length=40), nullable=False),
        sa.Column("outcome_date", sa.Date(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "outcome_type IN (" + ", ".join(f"'{value}'" for value in OUTCOME_VALUES) + ")",
            name="ck_ckd_registry_outcomes_type",
        ),
        sa.CheckConstraint(
            "outcome_date <= CURRENT_DATE",
            name="ck_ckd_registry_outcomes_date_not_future",
        ),
    )
    op.create_index(
        "ix_ckd_registry_outcomes_entry_date",
        "ckd_registry_outcomes",
        ["registry_entry_id", "outcome_date"],
    )
    op.create_index(
        "ix_ckd_registry_outcomes_type",
        "ckd_registry_outcomes",
        ["outcome_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_ckd_registry_outcomes_type", table_name="ckd_registry_outcomes")
    op.drop_index(
        "ix_ckd_registry_outcomes_entry_date",
        table_name="ckd_registry_outcomes",
    )
    op.drop_table("ckd_registry_outcomes")

    op.drop_index("ix_ckd_registry_entries_is_active", table_name="ckd_registry_entries")
    op.drop_index("ix_ckd_registry_entries_included_at", table_name="ckd_registry_entries")
    op.drop_table("ckd_registry_entries")

    # Перед возвратом старого CHECK новые роли преобразуем обратно во врача.
    op.execute(
        sa.text(
            "UPDATE users SET role = 'doctor' "
            "WHERE role IN ('chief_physician', 'department_head')"
        )
    )
    op.drop_constraint("chk_users_role_model", "users", type_="check")
    op.create_check_constraint("chk_users_role_model", "users", OLD_ROLE_CHECK)
