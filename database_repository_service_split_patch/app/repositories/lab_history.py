"""
Назначение файла: repository для чтения истории лабораторных и инструментальных данных.

Этот файл содержит только SELECT-запросы для истории:
- ОАК;
- биохимии;
- расчётных показателей;
- ОАМ;
- альбуминурии;
- УЗИ почек.

Что редактировать здесь:
- состав колонок историй анализов;
- сортировку историй;
- фильтр until_date;
- правила выбора записи, если за одну дату есть несколько анализов.

Что не редактировать здесь:
- INSERT-ы анализов — они остаются в app/repositories/labs.py;
- расчёты СКФ/ACR;
- прогноз ХБП;
- шаблоны и внешний вид карточки пациента.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.db.connection import get_db_connection


def _build_date_filter(column_sql: str, until_date: date | None, params: list[Any]) -> str:
    """Добавляет фильтр по дате, если карточка/экспорт смотрит историю до выбранного приёма."""
    if not until_date:
        return ""

    params.append(until_date)
    return f"AND {column_sql} <= %s"


def _fetch_patient_biochemistry_history(cur: Any, patient_id: int, until_date: date | None = None):
    """Возвращает историю биохимических анализов пациента через открытый cursor."""
    params: list[Any] = [patient_id]
    date_filter = _build_date_filter("bio.investigation_date", until_date, params)

    cur.execute(
        f"""
        SELECT
            bio.investigation_date,
            bio.creatinine,
            bio.urea,
            bio.uric_acid,
            bio.glucose,
            bio.total_protein,
            bio.albumin,
            bio.potassium,
            bio.calcium,
            bio.phosphorus,
            bio.ferritin,
            bio.ptg
        FROM biochemistry_results bio
        JOIN appointments a ON bio.appointment_id = a.id
        WHERE a.patient_id = %s
          AND bio.investigation_date IS NOT NULL
          {date_filter}
        ORDER BY bio.investigation_date ASC
        """,
        params,
    )
    return cur.fetchall()


def get_patient_biochemistry_history(patient_id: int, until_date: date | None = None):
    """Возвращает историю биохимических анализов пациента."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_patient_biochemistry_history(cur, patient_id, until_date)


def _fetch_patient_cbc_history(cur: Any, patient_id: int, until_date: date | None = None):
    """Возвращает историю общего анализа крови пациента через открытый cursor."""
    params: list[Any] = [patient_id]
    date_filter = _build_date_filter("cbc.investigation_date", until_date, params)

    cur.execute(
        f"""
        SELECT
            cbc.investigation_date,
            cbc.hemoglobin,
            cbc.erythrocytes,
            cbc.leukocytes,
            cbc.platelets,
            cbc.esr,
            cbc.mcv,
            cbc.hematocrit
        FROM cbc_results cbc
        JOIN appointments a ON cbc.appointment_id = a.id
        WHERE a.patient_id = %s
          AND cbc.investigation_date IS NOT NULL
          {date_filter}
        ORDER BY cbc.investigation_date ASC
        """,
        params,
    )
    return cur.fetchall()


def get_patient_cbc_history(patient_id: int, until_date: date | None = None):
    """Возвращает историю общего анализа крови пациента."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_patient_cbc_history(cur, patient_id, until_date)


def _fetch_patient_urinalysis_history(cur: Any, patient_id: int, until_date: date | None = None):
    """Возвращает историю ОАМ пациента через открытый cursor."""
    params: list[Any] = [patient_id]
    date_filter = _build_date_filter("uri.investigation_date", until_date, params)

    cur.execute(
        f"""
        SELECT DISTINCT ON (uri.investigation_date)
            uri.investigation_date,
            uri.specific_gravity,
            uri.protein,
            uri.leukocytes,
            uri.erythrocytes,
            uri.bacteria
        FROM urinalysis_results uri
        JOIN appointments a ON uri.appointment_id = a.id
        WHERE a.patient_id = %s
          AND uri.investigation_date IS NOT NULL
          {date_filter}
        ORDER BY uri.investigation_date ASC, uri.id DESC
        """,
        params,
    )
    return cur.fetchall()


def get_patient_urinalysis_history(patient_id: int, until_date: date | None = None):
    """Возвращает историю общего анализа мочи пациента."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_patient_urinalysis_history(cur, patient_id, until_date)


def _fetch_patient_metrics_history(cur: Any, patient_id: int, until_date: date | None = None):
    """Возвращает историю расчётных показателей пациента через открытый cursor."""
    params: list[Any] = [patient_id]
    date_filter = _build_date_filter("COALESCE(cm.investigation_date, a.appointment_date::date)", until_date, params)

    cur.execute(
        f"""
        SELECT
            COALESCE(cm.investigation_date, a.appointment_date::date) AS investigation_date,
            cm.creatinine,
            cm.egfr_ckdepi,
            cm.crcl_cockcroft_gault,
            cm.ckd_stage
        FROM calculated_metrics cm
        JOIN appointments a ON cm.appointment_id = a.id
        WHERE a.patient_id = %s
          {date_filter}
        ORDER BY COALESCE(cm.investigation_date, a.appointment_date::date) ASC
        """,
        params,
    )
    return cur.fetchall()


def get_patient_metrics_history(patient_id: int, until_date: date | None = None):
    """Возвращает историю расчётных показателей пациента."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_patient_metrics_history(cur, patient_id, until_date)


def save_calculated_metrics(appointment_id: int, egfr_ckdepi, crcl_cockcroft_gault, ckd_stage):
    """
    Старый публичный способ сохранения одной строки calculated_metrics.

    Оставлен для совместимости. Новая логика сохранения нескольких расчётов
    по датам находится в app/repositories/labs.py: insert_calculated_metric().
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO calculated_metrics (
                    appointment_id,
                    egfr_ckdepi,
                    crcl_cockcroft_gault,
                    ckd_stage
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (appointment_id) DO UPDATE SET
                    egfr_ckdepi = EXCLUDED.egfr_ckdepi,
                    crcl_cockcroft_gault = EXCLUDED.crcl_cockcroft_gault,
                    ckd_stage = EXCLUDED.ckd_stage
                """,
                (
                    appointment_id,
                    egfr_ckdepi,
                    crcl_cockcroft_gault,
                    ckd_stage,
                ),
            )


def _fetch_patient_ultrasound_history(cur: Any, patient_id: int, until_date: date | None = None):
    """Возвращает историю УЗИ почек пациента через открытый cursor."""
    params: list[Any] = [patient_id]
    date_filter = _build_date_filter("us.investigation_date", until_date, params)

    cur.execute(
        f"""
        SELECT
            us.investigation_date,
            us.left_kidney_size,
            us.right_kidney_size,
            us.left_parenchyma,
            us.right_parenchyma,
            us.description
        FROM ultrasound_results us
        JOIN appointments a ON us.appointment_id = a.id
        WHERE a.patient_id = %s
          AND us.investigation_date IS NOT NULL
          {date_filter}
        ORDER BY us.investigation_date ASC
        """,
        params,
    )
    return cur.fetchall()


def get_patient_ultrasound_history(patient_id: int, until_date: date | None = None):
    """Возвращает историю УЗИ почек пациента."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_patient_ultrasound_history(cur, patient_id, until_date)


def _fetch_patient_albuminuria_history(cur: Any, patient_id: int, until_date: date | None = None):
    """Возвращает историю альбуминурии пациента через открытый cursor."""
    params: list[Any] = [patient_id]
    date_filter = _build_date_filter("ar.investigation_date", until_date, params)

    cur.execute(
        f"""
        SELECT
            ar.investigation_date,
            ar.urine_albumin,
            ar.urine_albumin_unit,
            ar.urine_creatinine,
            ar.urine_creatinine_unit,
            ar.albumin_creatinine_ratio,
            ar.albuminuria_category
        FROM albuminuria_results ar
        JOIN appointments a ON ar.appointment_id = a.id
        WHERE a.patient_id = %s
          AND ar.investigation_date IS NOT NULL
          {date_filter}
        ORDER BY ar.investigation_date ASC, ar.id ASC
        """,
        params,
    )
    return cur.fetchall()


def get_patient_albuminuria_history(patient_id: int, until_date: date | None = None):
    """Возвращает историю альбуминурии пациента."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_patient_albuminuria_history(cur, patient_id, until_date)
