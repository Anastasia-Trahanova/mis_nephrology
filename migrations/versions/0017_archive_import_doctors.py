"""Добавить врачей, встречающихся только в архивных консультациях.

Revision ID: 0017_archive_import_doctors
Revises: 0016_archive_import_fields
"""

from __future__ import annotations

from alembic import op


revision = "0017_archive_import_doctors"
down_revision = "0016_archive_import_fields"
branch_labels = None
depends_on = None


_DOCTORS: tuple[tuple[str, str, str], ...] = (
    ("Белякова", "Е.", "С."),
    ("Гордеева", "Е.", "М."),
    ("Одинцова", "С.", "В."),
    ("Палавин", "А.", "С."),
    ("Родионова", "О.", "А."),
    ("Серова", "А.", "Б."),
    ("Юрченко", "М.", "Л."),
)


def upgrade() -> None:
    """Добавить отсутствующих врачей без создания учётных записей."""
    connection = op.get_bind()

    for last_name, first_name, patronymic in _DOCTORS:
        connection.exec_driver_sql(
            """
            INSERT INTO doctors (last_name, first_name, patronymic)
            SELECT %(last_name)s, %(first_name)s, %(patronymic)s
            WHERE NOT EXISTS (
                SELECT 1
                FROM doctors
                WHERE lower(trim(last_name)) = lower(trim(%(last_name)s))
                  AND lower(replace(trim(first_name), ' ', '')) =
                      lower(replace(trim(%(first_name)s), ' ', ''))
                  AND lower(replace(trim(coalesce(patronymic, '')), ' ', '')) =
                      lower(replace(trim(%(patronymic)s), ' ', ''))
            )
            """,
            {
                "last_name": last_name,
                "first_name": first_name,
                "patronymic": patronymic,
            },
        )


def downgrade() -> None:
    """Удалить добавленных врачей, если на них ещё нет ссылок."""
    connection = op.get_bind()

    for last_name, first_name, patronymic in reversed(_DOCTORS):
        connection.exec_driver_sql(
            """
            DELETE FROM doctors d
            WHERE lower(trim(d.last_name)) = lower(trim(%(last_name)s))
              AND lower(replace(trim(d.first_name), ' ', '')) =
                  lower(replace(trim(%(first_name)s), ' ', ''))
              AND lower(replace(trim(coalesce(d.patronymic, '')), ' ', '')) =
                  lower(replace(trim(%(patronymic)s), ' ', ''))
              AND NOT EXISTS (
                  SELECT 1 FROM appointments a WHERE a.doctor_id = d.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM users u WHERE u.doctor_id = d.id
              )
            """,
            {
                "last_name": last_name,
                "first_name": first_name,
                "patronymic": patronymic,
            },
        )
