"""Поля для импорта архивных консультаций нефролога.

Revision ID: 0016_archive_import_fields
Revises: 0015_grouped_prescriptions
Create Date: 2026-08-05

Назначение
----------
1. Разрешает NULL в поле пола пациента: для обычной формы обязательность
   остаётся задачей серверной валидации, а архивный импорт может создавать
   пациента без предположения пола.
2. Разрешает NULL для места приёма: в архивных документах место может быть
   не указано.
3. Добавляет свободные сводные поля анамнеза заболевания и анамнеза жизни,
   не заменяя существующие структурированные поля формы.
4. Добавляет исходную формулировку диагноза и комментарий к диагнозу без
   автоматического преобразования в МКБ-10.
5. Добавляет технические поля архивного импорта и уникальный ключ источника,
   чтобы повторный импорт не создавал дубли.

УЗИ и другие инструментальные исследования не получают нового столбца:
для них уже существует
appointment_additional_studies.other_instrumental_studies.

Наследственность хранится в surveys.heredity_description, рекомендации —
в appointment_diets.recommendations; миграция их не меняет.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_archive_import_fields"
down_revision = "0015_grouped_prescriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавляет поля, необходимые для архивного импорта."""

    # Архивный пациент может не иметь достоверно установленного пола.
    # Для обычного интерфейса обязательность будет сохранена в серверной
    # валидации приложения.
    op.alter_column(
        "patients",
        "gender",
        existing_type=sa.Boolean(),
        nullable=True,
    )

    # Место архивного приёма может отсутствовать. Внешний ключ сохраняется:
    # ненулевое значение по-прежнему обязано ссылаться на locations.id.
    op.alter_column(
        "appointments",
        "location_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    op.add_column(
        "surveys",
        sa.Column("disease_anamnesis_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "surveys",
        sa.Column("life_anamnesis_text", sa.Text(), nullable=True),
    )

    op.add_column(
        "appointments",
        sa.Column("diagnosis_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column("diagnosis_comment_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "is_archive_import",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "appointments",
        sa.Column("archive_import_key", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_appointments_archive_import_key",
        "appointments",
        ["archive_import_key"],
    )

    op.execute(
        "COMMENT ON COLUMN patients.gender "
        "IS 'Пол пациента; для архивного импорта может быть не указан';"
    )
    op.execute(
        "COMMENT ON COLUMN appointments.location_id "
        "IS 'Место проведения приёма; для архивного импорта может быть не указано';"
    )
    op.execute(
        "COMMENT ON COLUMN surveys.disease_anamnesis_text "
        "IS 'Анамнез заболевания: свободный текст из архивной консультации';"
    )
    op.execute(
        "COMMENT ON COLUMN surveys.life_anamnesis_text "
        "IS 'Анамнез жизни: свободный текст из архивной консультации';"
    )
    op.execute(
        "COMMENT ON COLUMN appointments.diagnosis_text "
        "IS 'Диагноз в исходной формулировке врача без автоматического кодирования МКБ-10';"
    )
    op.execute(
        "COMMENT ON COLUMN appointments.diagnosis_comment_text "
        "IS 'Пояснения и комментарии врача к диагнозу';"
    )
    op.execute(
        "COMMENT ON COLUMN appointments.is_archive_import "
        "IS 'Приём импортирован из архива консультаций';"
    )
    op.execute(
        "COMMENT ON COLUMN appointments.archive_import_key "
        "IS 'Уникальный технический ключ архивного приёма для защиты от повторного импорта';"
    )


def downgrade() -> None:
    """Удаляет добавленные поля и возвращает прежнюю обязательность."""

    # Не удаляем архивные медицинские данные молча. Если после импорта появились
    # NULL, сначала нужно удалить или исправить соответствующие архивные записи.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM patients WHERE gender IS NULL) THEN
                RAISE EXCEPTION
                    'Нельзя откатить 0016: существуют пациенты без указанного пола';
            END IF;
            IF EXISTS (SELECT 1 FROM appointments WHERE location_id IS NULL) THEN
                RAISE EXCEPTION
                    'Нельзя откатить 0016: существуют приёмы без места проведения';
            END IF;
        END
        $$;
        """
    )

    op.drop_constraint(
        "uq_appointments_archive_import_key",
        "appointments",
        type_="unique",
    )
    op.drop_column("appointments", "archive_import_key")
    op.drop_column("appointments", "is_archive_import")
    op.drop_column("appointments", "diagnosis_comment_text")
    op.drop_column("appointments", "diagnosis_text")

    op.drop_column("surveys", "life_anamnesis_text")
    op.drop_column("surveys", "disease_anamnesis_text")

    op.alter_column(
        "appointments",
        "location_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "patients",
        "gender",
        existing_type=sa.Boolean(),
        nullable=False,
    )
