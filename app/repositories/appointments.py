"""
Назначение файла: repository таблицы appointments и агрегированного чтения приёма.

Что выполняет файл
-------------------
Создаёт запись приёма и читает данные, необходимые форме повторного приёма,
карточке пациента и существующему Word-экспорту.

После миграции 0009 возраст хранится непосредственно у приёма. Полный SELECT
возвращает новые структурированные поля, а также временные вычисляемые алиасы
старых полей для совместимости Word-экспорта. Начиная с миграции 0011 запросы
также читают свободные описания других исследований. Сам модуль экспорта не
изменяется.
"""

from __future__ import annotations

from typing import Any

from app.db.connection import get_db_connection


def create_appointment(
    cur: Any,
    patient_id: int,
    doctor_id: int,
    location_id: int,
    appointment_datetime: Any,
    age_at_appointment: int,
) -> int:
    """Создаёт приём и сохраняет возраст пациента на дату этого приёма."""
    cur.execute(
        """
        INSERT INTO appointments (
            patient_id,
            doctor_id,
            location_id,
            appointment_date,
            age_at_appointment
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            patient_id,
            doctor_id,
            location_id,
            appointment_datetime,
            age_at_appointment,
        ),
    )
    return cur.fetchone()["id"]


def get_all_appointments(filters: dict | None = None):
    """Возвращает список приёмов с фильтрацией, сортировкой и пагинацией."""
    filters = filters or {}
    query = """
        SELECT
            a.id AS appointment_id,
            p.id AS patient_id,
            p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
            a.appointment_date,
            a.age_at_appointment AS age,
            d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_fio,
            l.name AS location_name,
            b.name AS branch_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN locations l ON a.location_id = l.id
        JOIN branches b ON l.branch_id = b.id
        WHERE 1=1
    """
    params: list[Any] = []

    if filters.get("branch_id"):
        query += " AND b.id = %s"
        params.append(filters["branch_id"])
    if filters.get("location_id"):
        query += " AND l.id = %s"
        params.append(filters["location_id"])
    if filters.get("doctor_id"):
        query += " AND d.id = %s"
        params.append(filters["doctor_id"])
    if filters.get("search"):
        query += """
            AND (
                p.last_name ILIKE %s
                OR p.first_name ILIKE %s
                OR COALESCE(p.patronymic, '') ILIKE %s
            )
        """
        search = f"%{filters['search']}%"
        params.extend([search, search, search])
    if filters.get("date_from"):
        query += " AND a.appointment_date >= %s"
        params.append(filters["date_from"])
    if filters.get("date_to"):
        query += " AND a.appointment_date < (%s::date + INTERVAL '1 day')"
        params.append(filters["date_to"])

    sort_order = str(filters.get("sort_order", "desc")).lower()
    sort_order = "ASC" if sort_order == "asc" else "DESC"
    try:
        limit = int(filters.get("limit") or 200)
    except (TypeError, ValueError):
        limit = 200
    limit = max(1, min(limit, 500))
    try:
        offset = int(filters.get("offset") or 0)
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)

    query += f" ORDER BY a.appointment_date {sort_order} LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def _fetch_patient_appointments(cur: Any, patient_id: int):
    """Возвращает приёмы пациента через уже открытый cursor."""
    cur.execute(
        """
        SELECT
            a.id AS appointment_id,
            a.appointment_date,
            d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_name,
            l.name AS location_name,
            b.name AS branch_name
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        JOIN locations l ON a.location_id = l.id
        JOIN branches b ON l.branch_id = b.id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC
        """,
        (patient_id,),
    )
    return cur.fetchall()


def get_patient_appointments(patient_id: int):
    """Возвращает все приёмы конкретного пациента."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_patient_appointments(cur, patient_id)


def _fetch_appointment_full_data(cur: Any, appointment_id: int):
    """Возвращает полные данные выбранного приёма и совместимые алиасы для Word."""
    cur.execute(
        """
        SELECT
            a.id,
            a.appointment_date,
            a.patient_id,
            a.location_id,
            a.age_at_appointment,
            p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
            p.birth_date,
            p.phone,
            d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_name,
            l.name AS location_name,
            b.name AS branch_name,

            s.complaints,
            s.education_and_professional_history,
            s.housing_conditions,
            s.past_diseases,
            s.habitual_intoxications,
            s.gynecological_history,
            s.heredity_description,
            s.family_life,
            s.allergological_history,
            s.epidemiological_history,
            s.insurance_history,
            s.disease_onset,
            s.disease_course,

            e.general_condition,
            e.consciousness,
            e.bed_position,
            e.bed_position_details,
            e.body_build,
            e.height,
            e.weight,
            e.bmi,
            e.constitution_type,
            e.skin_and_mucous_membranes,
            e.edema_location,
            e.lymph_nodes,
            e.thyroid_gland,
            e.musculoskeletal_system,
            e.body_temperature,
            e.systolic_pressure,
            e.diastolic_pressure,
            e.bp_note,
            e.heart_rate,
            e.veins_condition,
            e.lung_auscultation,
            e.abdomen,
            e.kidney_palpation,
            e.kidney_palpation_details,
            e.pasternatsky_result,
            e.pasternatsky_side,

            ad.diet,
            ad.next_control_date,
            ad.recommendations,
            ast.other_laboratory_studies,
            ast.other_instrumental_studies,

            /*
             * Временные алиасы только для старого Word-экспорта.
             * Они не являются столбцами БД и не используются при сохранении.
             */
            CONCAT_WS(E'\n',
                s.education_and_professional_history,
                s.housing_conditions,
                s.past_diseases,
                s.habitual_intoxications,
                s.gynecological_history,
                s.family_life,
                s.allergological_history,
                s.epidemiological_history,
                s.insurance_history
            ) AS life_anamnesis,
            CONCAT_WS(E'\n', s.disease_onset, s.disease_course) AS disease_anamnesis,
            NULL::text AS comorbidities,
            e.skin_and_mucous_membranes AS skin_condition
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN locations l ON a.location_id = l.id
        JOIN branches b ON l.branch_id = b.id
        LEFT JOIN surveys s ON a.id = s.appointment_id
        LEFT JOIN examinations e ON a.id = e.appointment_id
        LEFT JOIN appointment_diets ad ON a.id = ad.appointment_id
        LEFT JOIN appointment_additional_studies ast ON a.id = ast.appointment_id
        WHERE a.id = %s
        """,
        (appointment_id,),
    )
    return cur.fetchone()


def get_appointment_full_data(appointment_id: int):
    """Возвращает основные данные одного приёма."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_appointment_full_data(cur, appointment_id)


def _fetch_last_appointment_data(cur: Any, patient_id: int):
    """Возвращает последний приём для автоподстановки новой формы."""
    cur.execute(
        """
        SELECT
            a.id AS appointment_id,
            a.doctor_id,
            a.location_id,
            a.appointment_date,
            s.complaints,
            s.education_and_professional_history,
            s.housing_conditions,
            s.past_diseases,
            s.habitual_intoxications,
            s.gynecological_history,
            s.heredity_description,
            s.family_life,
            s.allergological_history,
            s.epidemiological_history,
            s.insurance_history,
            s.disease_onset,
            s.disease_course,
            e.general_condition,
            e.consciousness,
            e.bed_position,
            e.bed_position_details,
            e.body_build,
            e.height,
            e.weight,
            e.bmi,
            e.constitution_type,
            e.skin_and_mucous_membranes,
            e.edema_location,
            e.lymph_nodes,
            e.thyroid_gland,
            e.musculoskeletal_system,
            e.body_temperature,
            e.systolic_pressure,
            e.diastolic_pressure,
            e.bp_note,
            e.heart_rate,
            e.veins_condition,
            e.lung_auscultation,
            e.abdomen,
            e.kidney_palpation,
            e.kidney_palpation_details,
            e.pasternatsky_result,
            e.pasternatsky_side,
            ad.diet,
            ad.next_control_date,
            ad.recommendations,
            ast.other_laboratory_studies,
            ast.other_instrumental_studies
        FROM appointments a
        LEFT JOIN surveys s ON a.id = s.appointment_id
        LEFT JOIN examinations e ON a.id = e.appointment_id
        LEFT JOIN appointment_diets ad ON a.id = ad.appointment_id
        LEFT JOIN appointment_additional_studies ast ON a.id = ast.appointment_id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC
        LIMIT 1
        """,
        (patient_id,),
    )
    return cur.fetchone()


def get_last_appointment_data(patient_id: int):
    """Возвращает данные последнего приёма пациента."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_last_appointment_data(cur, patient_id)


def _fetch_appointment_medications(cur: Any, appointment_id: int):
    """Возвращает лекарства приёма через уже открытый cursor."""
    cur.execute(
        """
        SELECT id, medication, dosage, schedule
        FROM prescriptions
        WHERE appointment_id = %s
        ORDER BY id
        """,
        (appointment_id,),
    )
    return cur.fetchall()


def get_appointment_medications(appointment_id: int):
    """Возвращает список лекарств для приёма."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_appointment_medications(cur, appointment_id)


def _fetch_appointment_diet(cur: Any, appointment_id: int):
    """Возвращает диету, дату контроля и рекомендации приёма."""
    cur.execute(
        """
        SELECT diet, next_control_date, recommendations
        FROM appointment_diets
        WHERE appointment_id = %s
        LIMIT 1
        """,
        (appointment_id,),
    )
    return cur.fetchone()


def get_appointment_diet(appointment_id: int):
    """Возвращает диету, дату контроля и рекомендации."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_appointment_diet(cur, appointment_id)
