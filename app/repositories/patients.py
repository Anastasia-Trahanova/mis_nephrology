"""
Repository для таблицы patients.

На втором этапе форма начинает сохранять телефон нового пациента в уже
существующий столбец patients.phone. Другие контактные таблицы и поля не
создаются.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.db.connection import get_db_connection


def create_patient(cur: Any, patient_data: dict[str, Any]) -> int:
    """Создаёт пациента и возвращает его id."""
    cur.execute(
        """
        INSERT INTO patients (
            last_name,
            first_name,
            patronymic,
            birth_date,
            gender,
            phone
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            patient_data["last_name"],
            patient_data["first_name"],
            patient_data["patronymic"],
            patient_data["birth_date"],
            patient_data["gender"],
            patient_data.get("phone"),
        ),
    )
    return cur.fetchone()["id"]


def get_patient_for_appointment(cur: Any, patient_id: int) -> dict[str, Any] | None:
    """Возвращает минимальные данные пациента для создания нового приёма."""
    cur.execute(
        """
        SELECT id, birth_date, gender
        FROM patients
        WHERE id = %s
        """,
        (patient_id,),
    )
    return cur.fetchone()


def get_all_patients(search: str | None = None, limit: int = 500, offset: int = 0):
    """Возвращает список пациентов для страницы /patients."""
    limit = max(1, min(int(limit or 500), 1000))
    offset = max(0, int(offset or 0))

    query = """
        SELECT id, last_name, first_name, patronymic, birth_date, phone
        FROM patients
        WHERE 1=1
    """
    params: list[Any] = []

    if search:
        query += """
            AND (
                last_name ILIKE %s
                OR first_name ILIKE %s
                OR patronymic ILIKE %s
                OR phone ILIKE %s
            )
        """
        value = f"%{search}%"
        params.extend([value, value, value, value])

    query += """
        ORDER BY last_name, first_name, patronymic NULLS LAST
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def _add_age(patient_data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Добавляет текущий возраст к словарю пациента для интерфейса."""
    if not patient_data:
        return patient_data

    birth_date = patient_data.get("birth_date")
    if birth_date:
        today = date.today()
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        patient_data["age"] = age
    else:
        patient_data["age"] = None
    return patient_data


def _fetch_patient_by_id(cur: Any, patient_id: int):
    """Возвращает основные данные пациента через уже открытый cursor."""
    cur.execute(
        """
        SELECT
            id,
            last_name,
            first_name,
            patronymic,
            birth_date,
            phone,
            CASE WHEN gender THEN 'Мужской' ELSE 'Женский' END AS gender_str
        FROM patients
        WHERE id = %s
        """,
        (patient_id,),
    )
    return _add_age(cur.fetchone())


def get_patient_by_id(patient_id: int):
    """Возвращает основные данные пациента для карточки."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_patient_by_id(cur, patient_id)


def get_patient_contact_info(patient_id: int):
    """Возвращает контактные данные пациента отдельно от основной карточки."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT phone, email
                FROM patients
                WHERE id = %s
                """,
                (patient_id,),
            )
            return cur.fetchone()
