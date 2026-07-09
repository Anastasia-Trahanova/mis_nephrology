"""
Назначение файла: repository для справочных данных.

Этот файл содержит SQL-запросы к справочникам и словарям:
- филиалы;
- отделения;
- врачи;
- связка врачей и отделений;
- информация об отделении/филиале/компании;
- справочник диагнозов МКБ-10;
- справочник лекарств;
- структурированные МКБ-10 диагнозы конкретного приёма.
"""

from __future__ import annotations

from typing import Any

from app.db.connection import get_db_connection


def _fetch_branches(cur: Any):
    """Возвращает список филиалов через уже открытый cursor."""
    cur.execute("SELECT id, name FROM branches ORDER BY name")
    return cur.fetchall()


def get_branches():
    """Возвращает список филиалов для фильтров и форм."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_branches(cur)


def _fetch_locations_by_branch(cur: Any, branch_id: int | None = None):
    """Возвращает отделения через уже открытый cursor."""
    if branch_id:
        cur.execute(
            "SELECT id, name, branch_id FROM locations WHERE branch_id = %s ORDER BY name",
            (branch_id,),
        )
    else:
        cur.execute("SELECT id, name, branch_id FROM locations ORDER BY name")
    return cur.fetchall()


def get_locations_by_branch(branch_id: int | None = None):
    """Возвращает отделения, при необходимости только для выбранного филиала."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_locations_by_branch(cur, branch_id)


def _fetch_doctors(cur: Any):
    """Возвращает список врачей через уже открытый cursor."""
    cur.execute("SELECT id, last_name, first_name, patronymic FROM doctors ORDER BY last_name")
    return cur.fetchall()


def get_doctors():
    """Возвращает список врачей для форм."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_doctors(cur)


def _fetch_doctor_by_id(cur: Any, doctor_id: int):
    """Возвращает одного врача по id через уже открытый cursor."""
    cur.execute(
        """
        SELECT id, last_name, first_name, patronymic
        FROM doctors
        WHERE id = %s
        LIMIT 1
        """,
        (doctor_id,),
    )
    return cur.fetchone()


def get_doctor_by_id(doctor_id: int):
    """Возвращает одного врача по id."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_doctor_by_id(cur, doctor_id)


def get_doctors_for_filter(branch_id: int | None = None, location_id: int | None = None):
    """Возвращает врачей для фильтра главной страницы."""
    query = """
        SELECT DISTINCT d.id, d.last_name, d.first_name, d.patronymic
        FROM doctors d
        LEFT JOIN doctor_locations dl ON dl.doctor_id = d.id
        LEFT JOIN locations l ON l.id = dl.location_id
        WHERE 1=1
    """
    params: list[Any] = []

    if branch_id:
        query += " AND l.branch_id = %s"
        params.append(branch_id)

    if location_id:
        query += " AND dl.location_id = %s"
        params.append(location_id)

    query += " ORDER BY d.last_name, d.first_name, d.patronymic"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def get_locations_for_filter(branch_id: int | None = None, doctor_id: int | None = None):
    """Возвращает отделения для фильтра главной страницы."""
    query = """
        SELECT DISTINCT l.id, l.name, l.branch_id
        FROM locations l
        LEFT JOIN doctor_locations dl ON dl.location_id = l.id
        WHERE 1=1
    """
    params: list[Any] = []

    if branch_id:
        query += " AND l.branch_id = %s"
        params.append(branch_id)

    if doctor_id:
        query += " AND dl.doctor_id = %s"
        params.append(doctor_id)

    query += " ORDER BY l.name"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def _fetch_doctor_locations(cur: Any, doctor_id: int):
    """Возвращает отделения текущего врача через уже открытый cursor."""
    cur.execute(
        """
        SELECT l.id, l.name, l.branch_id, b.name AS branch_name
        FROM doctor_locations dl
        JOIN locations l ON dl.location_id = l.id
        JOIN branches b ON l.branch_id = b.id
        WHERE dl.doctor_id = %s
        ORDER BY b.name, l.name
        """,
        (doctor_id,),
    )
    return cur.fetchall()


def get_doctor_locations(doctor_id: int):
    """Возвращает отделения, где работает выбранный врач."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_doctor_locations(cur, doctor_id)


def doctor_can_work_in_location(cur: Any, doctor_id: int, location_id: int) -> bool:
    """Проверяет, что отделение действительно привязано к врачу."""
    cur.execute(
        """
        SELECT 1
        FROM doctor_locations
        WHERE doctor_id = %s
          AND location_id = %s
        LIMIT 1
        """,
        (doctor_id, location_id),
    )
    return cur.fetchone() is not None


def get_location_info(location_id: int):
    """Возвращает информацию об отделении, филиале и компании для карточки/экспорта."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    l.id,
                    l.name AS location_name,
                    l.factual_address AS location_address,
                    b.id AS branch_id,
                    b.name AS branch_name,
                    b.legal_address AS branch_address,
                    b.phone AS branch_phone,
                    b.email AS branch_email,
                    c.id AS company_id,
                    c.name AS company_name,
                    c.legal_address AS company_address,
                    c.phone AS company_phone,
                    c.email AS company_email
                FROM locations l
                LEFT JOIN branches b ON l.branch_id = b.id
                LEFT JOIN companies c ON b.company_id = c.id
                WHERE l.id = %s
                """,
                (location_id,),
            )
            return cur.fetchone()


def _fetch_icd10_diagnoses(cur: Any):
    """Возвращает активный справочник диагнозов МКБ-10 для формы."""
    cur.execute(
        """
        SELECT id, diagnosis
        FROM icd10_diagnoses
        WHERE is_active = TRUE
        ORDER BY diagnosis
        """
    )
    return cur.fetchall()


def get_icd10_diagnoses():
    """Публичная обёртка для получения справочника МКБ-10."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_icd10_diagnoses(cur)


def _fetch_appointment_icd10_diagnoses(cur: Any, appointment_id: int):
    """Возвращает структурированные МКБ-10 диагнозы выбранного приёма."""
    cur.execute(
        """
        SELECT
            id,
            appointment_id,
            diagnosis_type,
            icd10_diagnosis_id,
            icd10_diagnosis,
            doctor_note,
            sort_order
        FROM appointment_icd10_diagnoses_view
        WHERE appointment_id = %s
        ORDER BY
            CASE diagnosis_type
                WHEN 'main' THEN 1
                WHEN 'complication' THEN 2
                WHEN 'comorbidity' THEN 3
                ELSE 4
            END,
            sort_order,
            id
        """,
        (appointment_id,),
    )
    return cur.fetchall()


def get_appointment_icd10_diagnoses(appointment_id: int):
    """Публичная обёртка для получения структурированных диагнозов приёма."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_appointment_icd10_diagnoses(cur, appointment_id)


def _fetch_medications_dictionary(cur: Any):
    """Возвращает активный справочник лекарств для формы назначений."""
    cur.execute(
        """
        SELECT id, display_name, trade_name, active_substance, drug_group
        FROM medications
        WHERE is_active = TRUE
        ORDER BY sort_order, display_name
        """
    )
    return cur.fetchall()


def get_medications_dictionary():
    """Публичная обёртка для получения справочника лекарств."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_medications_dictionary(cur)
