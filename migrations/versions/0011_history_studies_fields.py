"""Поля исследований из утверждённой схемы истории болезни.

Revision ID: 0011_history_studies_fields
Revises: 0010_remove_heredity_flag
Create Date: 2026-07-24

Назначение файла
----------------
1. Добавляет суточную экскрецию альбумина к конкретному результату
   альбуминурии.
2. Создаёт отдельную таблицу для свободного описания других лабораторных и
   инструментальных исследований выбранного приёма.

Что важно
---------
- существующие таблицы ОАК, ОАМ, биохимии, УЗИ и KDIGO не перестраиваются;
- лекарства и назначения миграция не затрагивает;
- все новые медицинские поля необязательные;
- downgrade удаляет только объекты, созданные этой миграцией.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_history_studies_fields"
down_revision = "0010_remove_heredity_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавляет суточную альбуминурию и свободные поля исследований."""
    op.add_column(
        "albuminuria_results",
        sa.Column("daily_albumin_excretion", sa.Numeric(12, 2), nullable=True),
    )
    op.create_check_constraint(
        "ck_albuminuria_daily_albumin_excretion_nonnegative",
        "albuminuria_results",
        "daily_albumin_excretion IS NULL OR daily_albumin_excretion >= 0",
    )
    op.execute(
        "COMMENT ON COLUMN albuminuria_results.daily_albumin_excretion "
        "IS 'Суточная экскреция альбумина, мг/сут';"
    )

    op.create_table(
        "appointment_additional_studies",
        sa.Column(
            "appointment_id",
            sa.Integer(),
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("other_laboratory_studies", sa.Text(), nullable=True),
        sa.Column("other_instrumental_studies", sa.Text(), nullable=True),
    )
    op.execute(
        "COMMENT ON TABLE appointment_additional_studies "
        "IS 'Свободные описания дополнительных исследований конкретного приёма';"
    )
    op.execute(
        "COMMENT ON COLUMN appointment_additional_studies.other_laboratory_studies "
        "IS 'Другие лабораторные исследования';"
    )
    op.execute(
        "COMMENT ON COLUMN appointment_additional_studies.other_instrumental_studies "
        "IS 'Другие инструментальные исследования';"
    )


def downgrade() -> None:
    """Удаляет только поля и таблицу, добавленные ревизией 0011."""
    op.drop_table("appointment_additional_studies")
    op.drop_constraint(
        "ck_albuminuria_daily_albumin_excretion_nonnegative",
        "albuminuria_results",
        type_="check",
    )
    op.drop_column("albuminuria_results", "daily_albumin_excretion")
