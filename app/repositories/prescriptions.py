"""
Repository для диеты, рекомендаций и лекарственных назначений.

Сейчас назначения сохраняются как свободный текст в prescriptions.medication.
Это сделано намеренно: привязку к medications.id лучше делать отдельной
миграцией и отдельным продуктовым этапом.
"""

from __future__ import annotations

from typing import Any


def insert_diet_and_recommendations(cur: Any, appointment_id: int, diet_data: dict[str, Any]) -> None:
    """Сохраняет диету, дату следующего контроля и рекомендации."""
    cur.execute(
        """
        INSERT INTO appointment_diets (appointment_id, diet, next_control_date, recommendations)
        VALUES (%s, %s, %s, %s)
        """,
        (
            appointment_id,
            diet_data.get("diet"),
            diet_data.get("next_control_date"),
            diet_data.get("recommendations"),
        ),
    )


def insert_prescription(
    cur: Any,
    appointment_id: int,
    medication: str | None,
    dosage: str | None,
    schedule: str | None,
) -> None:
    """Сохраняет одну строку лекарственного назначения."""
    cur.execute(
        """
        INSERT INTO prescriptions (appointment_id, medication, dosage, schedule)
        VALUES (%s, %s, %s, %s)
        """,
        (appointment_id, medication, dosage, schedule),
    )
