"""drop legacy free-text diagnoses table

Revision ID: 0004_drop_text_diagnoses
Revises: 0003_kdigo_risk_sources
Create Date: 2026-07-07

Назначение миграции
-------------------
Удаляет legacy-таблицу diagnoses со свободными текстовыми формулировками
диагнозов. Источник истины по диагнозам после этой миграции — справочник
icd10_diagnoses и связующая таблица appointment_icd10_diagnoses.

Важно
-----
Перед применением миграции код приложения должен быть обновлен так, чтобы он
не делал INSERT/SELECT/JOIN к таблице diagnoses.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_drop_text_diagnoses"
down_revision = "0003_kdigo_risk_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS diagnoses CASCADE;")


def downgrade() -> None:
    op.create_table(
        "diagnoses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("main_diagnosis", sa.Text(), nullable=True),
        sa.Column("complications", sa.Text(), nullable=True),
        sa.Column("comorbidities", sa.Text(), nullable=True),
    )
    op.execute(
        """
        ALTER TABLE diagnoses
        ADD CONSTRAINT fk_diagnoses_appointment
        FOREIGN KEY (appointment_id) REFERENCES appointments(id)
        ON DELETE CASCADE;
        """
    )
    op.execute(
        """
        ALTER TABLE diagnoses
        ADD CONSTRAINT uq_diagnoses_appointment
        UNIQUE (appointment_id);
        """
    )
    op.execute(
        """
        ALTER TABLE diagnoses
        ADD CONSTRAINT chk_diagnoses_main_not_blank
        CHECK (main_diagnosis IS NULL OR LENGTH(TRIM(main_diagnosis)) > 0);
        """
    )
    op.create_index(
        "idx_diagnoses_appointment_id",
        "diagnoses",
        ["appointment_id"],
    )
