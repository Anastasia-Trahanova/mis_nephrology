"""
Repository для таблицы appointments.

Файл содержит только SQL создания/извлечения приёмов. Логика того, что именно
сохранять внутри приёма, остаётся в appointment_save_service.py.
"""

from __future__ import annotations

from typing import Any


def create_appointment(
    cur: Any,
    patient_id: int,
    doctor_id: int,
    location_id: int,
    appointment_datetime: Any,
) -> int:
    """Создаёт приём и возвращает его id."""
    cur.execute(
        """
        INSERT INTO appointments (
            patient_id,
            doctor_id,
            location_id,
            appointment_date
        )
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (
            patient_id,
            doctor_id,
            location_id,
            appointment_datetime,
        ),
    )
    return cur.fetchone()["id"]
