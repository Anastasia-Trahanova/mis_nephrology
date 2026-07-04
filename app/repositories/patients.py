"""
Repository для таблицы patients.

Этот файл нужен, чтобы убрать SQL по пациентам из сервисов и роутеров.
Здесь нет логики формы, медицинских расчётов и redirect-ов: только операции
с таблицей patients.
"""

from __future__ import annotations

from typing import Any


def create_patient(cur: Any, patient_data: dict[str, Any]) -> int:
    """Создаёт пациента и возвращает его id."""
    cur.execute(
        """
        INSERT INTO patients (
            last_name,
            first_name,
            patronymic,
            birth_date,
            gender
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            patient_data["last_name"],
            patient_data["first_name"],
            patient_data["patronymic"],
            patient_data["birth_date"],
            patient_data["gender"],
        ),
    )
    return cur.fetchone()["id"]


def get_patient_for_appointment(cur: Any, patient_id: int) -> dict[str, Any] | None:
    """
    Возвращает минимальные данные пациента, нужные для создания приёма.

    Сейчас для расчётов нужны birth_date и gender.
    """
    cur.execute(
        """
        SELECT id, birth_date, gender
        FROM patients
        WHERE id = %s
        """,
        (patient_id,),
    )
    return cur.fetchone()
