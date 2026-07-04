"""
Repository для таблицы examinations.

Здесь сохраняются данные объективного осмотра: кожа, отёки, давление, ЧСС,
рост, вес и серверно рассчитанный ИМТ.
"""

from __future__ import annotations

from typing import Any


def insert_examination(cur: Any, appointment_id: int, examination_data: dict[str, Any]) -> None:
    """Сохраняет раздел «Осмотр» одного приёма."""
    cur.execute(
        """
        INSERT INTO examinations (
            appointment_id,
            skin_condition,
            edema_location,
            systolic_pressure,
            diastolic_pressure,
            bp_note,
            heart_rate,
            height,
            weight,
            bmi
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            appointment_id,
            examination_data.get("skin_condition"),
            examination_data.get("edema_location"),
            examination_data.get("systolic_pressure"),
            examination_data.get("diastolic_pressure"),
            examination_data.get("bp_note"),
            examination_data.get("heart_rate"),
            examination_data.get("height"),
            examination_data.get("weight"),
            examination_data.get("bmi"),
        ),
    )
