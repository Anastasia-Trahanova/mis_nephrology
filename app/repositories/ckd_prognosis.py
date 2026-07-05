"""
Назначение файла: repository для сохранённого прогноза ХБП по KDIGO.

Этот файл временно содержит текущую SQL-логику прогноза ХБП:
- выбор последней категории СКФ;
- выбор последней категории альбуминурии;
- сохранение прогноза для приёма;
- получение прогноза выбранного приёма;
- получение истории прогнозов пациента.

Важно:
логика прогноза ХБП ещё будет отдельно пересматриваться. Сейчас цель файла —
вынести этот блок из app/database.py в одно понятное место, не меняя схему БД.

Что редактировать здесь:
- SQL выбора категорий СКФ/альбуминурии;
- порядок выбора последнего прогноза;
- способ удаления/перезаписи прогноза при пересчёте.

Что не редактировать здесь:
- матрицу медицинского прогноза — она находится в app/calculations.py;
- сохранение анализов;
- шаблоны карточки пациента.
"""

from __future__ import annotations

from typing import Any

from app.calculations import calculate_ckd_prognosis, normalize_ckd_stage_for_storage
from app.db.connection import get_db_connection


def _fetch_latest_gfr_category_for_prognosis(cur: Any, patient_id: int, assessment_date):
    """Берёт последнюю категорию СКФ пациента на дату прогноза или раньше."""
    cur.execute(
        """
        SELECT
            cm.ckd_stage,
            COALESCE(cm.investigation_date, a.appointment_date::date) AS investigation_date
        FROM calculated_metrics cm
        JOIN appointments a ON cm.appointment_id = a.id
        WHERE a.patient_id = %s
          AND cm.ckd_stage IS NOT NULL
          AND COALESCE(cm.investigation_date, a.appointment_date::date) <= %s
        ORDER BY COALESCE(cm.investigation_date, a.appointment_date::date) DESC, cm.id DESC
        LIMIT 1
        """,
        (patient_id, assessment_date),
    )
    return cur.fetchone()


def _fetch_latest_albuminuria_category_for_prognosis(cur: Any, patient_id: int, assessment_date):
    """Берёт последнюю категорию альбуминурии пациента на дату прогноза или раньше."""
    cur.execute(
        """
        SELECT
            ar.albuminuria_category,
            ar.investigation_date
        FROM albuminuria_results ar
        JOIN appointments a ON ar.appointment_id = a.id
        WHERE a.patient_id = %s
          AND ar.albuminuria_category IS NOT NULL
          AND ar.investigation_date <= %s
        ORDER BY ar.investigation_date DESC, ar.id DESC
        LIMIT 1
        """,
        (patient_id, assessment_date),
    )
    return cur.fetchone()


def save_ckd_prognosis_for_appointment(appointment_id: int, cur: Any | None = None):
    """
    Сохраняет прогноз ХБП по KDIGO для конкретного приёма.

    Сейчас прогноз строится по последней СКФ и последней альбуминурии
    внутри текущего приёма. Если данных недостаточно, возвращает None.
    """

    def _save(cursor: Any):
        cursor.execute(
            """
            SELECT investigation_date, ckd_stage
            FROM calculated_metrics
            WHERE appointment_id = %s
              AND ckd_stage IS NOT NULL
            ORDER BY investigation_date DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (appointment_id,),
        )
        metric = cursor.fetchone()

        cursor.execute(
            """
            SELECT investigation_date, albuminuria_category
            FROM albuminuria_results
            WHERE appointment_id = %s
              AND albuminuria_category IS NOT NULL
            ORDER BY investigation_date DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (appointment_id,),
        )
        albuminuria = cursor.fetchone()

        if not metric or not albuminuria:
            return None

        gfr_category = normalize_ckd_stage_for_storage(metric.get("ckd_stage"))
        albuminuria_category = albuminuria.get("albuminuria_category")
        prognosis = calculate_ckd_prognosis(gfr_category, albuminuria_category)

        if not prognosis or not prognosis.get("prognosis_level"):
            return None

        metric_date = metric.get("investigation_date")
        albuminuria_date = albuminuria.get("investigation_date")
        assessment_date = albuminuria_date or metric_date

        if metric_date and albuminuria_date:
            assessment_date = max(metric_date, albuminuria_date)

        cursor.execute(
            """
            DELETE FROM ckd_prognosis_results
            WHERE appointment_id = %s
            """,
            (appointment_id,),
        )

        cursor.execute(
            """
            INSERT INTO ckd_prognosis_results (
                appointment_id,
                assessment_date,
                gfr_category,
                albuminuria_category,
                combined_category,
                prognosis_level,
                prognosis_text,
                created_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
            )
            RETURNING *
            """,
            (
                appointment_id,
                assessment_date,
                prognosis["gfr_category"],
                prognosis["albuminuria_category"],
                prognosis["combined_category"],
                prognosis["prognosis_level"],
                prognosis["prognosis_text"],
            ),
        )
        return cursor.fetchone()

    if cur is not None:
        return _save(cur)

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            return _save(cursor)


def recalculate_ckd_prognosis_for_appointment(appointment_id: int, assessment_date=None):
    """
    Публичная функция для пересчёта прогноза одного приёма.

    Параметр assessment_date оставлен для совместимости со старым вызовом,
    но текущая логика берёт дату оценки из дат СКФ/альбуминурии внутри приёма.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return save_ckd_prognosis_for_appointment(appointment_id, cur=cur)


def _fetch_appointment_ckd_prognosis(cur: Any, appointment_id: int):
    """Возвращает сохранённый прогноз ХБП выбранного приёма через открытый cursor."""
    cur.execute(
        """
        SELECT
            id,
            appointment_id,
            assessment_date,
            gfr_category,
            albuminuria_category,
            combined_category,
            prognosis_level,
            prognosis_text
        FROM ckd_prognosis_results
        WHERE appointment_id = %s
        LIMIT 1
        """,
        (appointment_id,),
    )
    return cur.fetchone()


def get_appointment_ckd_prognosis(appointment_id: int):
    """Возвращает сохранённый прогноз ХБП для конкретного приёма."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_appointment_ckd_prognosis(cur, appointment_id)


def _fetch_patient_ckd_prognosis_history(cur: Any, patient_id: int, until_date=None):
    """Возвращает историю прогнозов ХБП пациента через открытый cursor."""
    params: list[Any] = [patient_id]
    date_filter = ""

    if until_date:
        date_filter = "AND cpr.assessment_date <= %s"
        params.append(until_date)

    cur.execute(
        f"""
        SELECT
            cpr.id,
            cpr.appointment_id,
            cpr.assessment_date,
            cpr.gfr_category,
            cpr.albuminuria_category,
            cpr.combined_category,
            cpr.prognosis_level,
            cpr.prognosis_text
        FROM ckd_prognosis_results cpr
        JOIN appointments a ON cpr.appointment_id = a.id
        WHERE a.patient_id = %s
          {date_filter}
        ORDER BY cpr.assessment_date ASC, cpr.id ASC
        """,
        params,
    )
    return cur.fetchall()


def get_patient_ckd_prognosis_history(patient_id: int, until_date=None):
    """Возвращает историю прогнозов ХБП пациента."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_patient_ckd_prognosis_history(cur, patient_id, until_date)
