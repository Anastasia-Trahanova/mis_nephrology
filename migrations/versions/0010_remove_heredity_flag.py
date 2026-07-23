"""Удаление отдельного булевого признака наследственности.

Revision ID: 0010_remove_heredity_flag
Revises: 0009_previsit_form_schema
Create Date: 2026-07-23

После этой миграции единственным источником истины становится свободный текст
``surveys.heredity_description``. Врач может указать как отягощённую, так и
неотягощённую наследственность, отсутствие данных или прочерк без дублирующей
галочки и без риска противоречия между двумя полями.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_remove_heredity_flag"
down_revision = "0009_previsit_form_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Оставляет наследственность только как свободное текстовое описание."""
    op.drop_constraint(
        "chk_surveys_heredity_description",
        "surveys",
        type_="check",
    )
    op.drop_column("surveys", "heredity")
    op.execute(
        "COMMENT ON COLUMN surveys.heredity_description "
        "IS 'Наследственность: свободное текстовое описание врача';"
    )


def downgrade() -> None:
    """Возвращает структуру 0009, сохраняя имеющийся текст наследственности."""
    op.add_column(
        "surveys",
        sa.Column(
            "heredity",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
        ),
    )

    # Для совместимости со старой схемой любой непустой текст считается
    # описанием отягощённой наследственности. Это техническое правило отката,
    # а не медицинская интерпретация текста.
    op.execute(
        """
        UPDATE surveys
        SET heredity = CASE
            WHEN NULLIF(BTRIM(heredity_description), '') IS NOT NULL THEN TRUE
            ELSE FALSE
        END;
        """
    )
    op.alter_column(
        "surveys",
        "heredity",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    op.create_check_constraint(
        "chk_surveys_heredity_description",
        "surveys",
        """
        (heredity = TRUE AND NULLIF(BTRIM(heredity_description), '') IS NOT NULL)
        OR (heredity = FALSE AND heredity_description IS NULL)
        """,
    )
    op.execute(
        "COMMENT ON COLUMN surveys.heredity "
        "IS 'Признак отягощённой наследственности';"
    )
    op.execute(
        "COMMENT ON COLUMN surveys.heredity_description "
        "IS 'Описание наследственности';"
    )
