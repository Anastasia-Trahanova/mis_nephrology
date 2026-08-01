"""
Repository для диеты, рекомендаций и лекарственных назначений.

Названия препаратов сохраняются свободным текстом, а therapy_group хранит
медицинскую цель конкретного назначения.
"""

from __future__ import annotations

from typing import Any

from app.db.connection import get_db_connection


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
    therapy_group: str,
    medication: str | None,
    dosage: str | None,
    schedule: str | None,
) -> None:
    """Сохраняет одну строку лекарственного назначения вместе с группой."""
    cur.execute(
        """
        INSERT INTO prescriptions (
            appointment_id,
            therapy_group,
            medication,
            dosage,
            schedule
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (appointment_id, therapy_group, medication, dosage, schedule),
    )


def _fetch_appointment_medications(cur: Any, appointment_id: int):
    """Возвращает назначения приёма с сохранёнными группами."""
    cur.execute(
        """
        SELECT id, therapy_group, medication, dosage, schedule
        FROM prescriptions
        WHERE appointment_id = %s
        ORDER BY id
        """,
        (appointment_id,),
    )
    return cur.fetchall()


def get_appointment_medications(appointment_id: int):
    """Публичная обёртка для получения назначений приёма."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_appointment_medications(cur, appointment_id)
