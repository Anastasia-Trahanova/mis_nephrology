"""
Назначение файла: repository для сохранённых оценок риска по KDIGO.

Что выполняет файл:
- ищет новые СКФ и альбуминурию внутри текущего приёма;
- если одного показателя нет, ищет последний подходящий показатель пациента
  в предыдущих приёмах;
- сохраняет все допустимые комбинации СКФ × альбуминурия в ckd_prognosis_results;
- хранит строгие источники расчёта: id строки СКФ, дату СКФ, id строки
  альбуминурии, дату альбуминурии, итоговую категорию и уровень риска;
- возвращает текущую оценку и историю оценок для карточки пациента;
- умеет помечать строку как скрытую, если врач решил убрать шум.

Что редактировать здесь:
- SQL выбора источников СКФ и альбуминурии;
- правила сохранения нескольких комбинаций на одном приёме;
- порядок отображения сохранённых строк.

Что не редактировать здесь:
- медицинскую матрицу KDIGO и фразы — они в app/medical_algorithms/kdigo_risk.py;
- сохранение самих анализов — оно в app/repositories/labs.py;
- HTML и JavaScript.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from app.db.connection import get_db_connection
from app.medical_algorithms.kdigo_risk import (
    build_source_pair_key,
    calculate_kdigo_risk,
    format_risk_phrase,
    is_interval_allowed,
    normalize_albuminuria_category,
    source_interval_days,
)
from app.medical_algorithms.ckd_stage import normalize_ckd_stage_for_storage


def _fetch_appointment_patient_and_date(cur: Any, appointment_id: int):
    """Возвращает patient_id и дату приёма для оценки KDIGO."""
    cur.execute(
        """
        SELECT
            a.id AS appointment_id,
            a.patient_id,
            a.appointment_date::date AS appointment_date
        FROM appointments a
        WHERE a.id = %s
        """,
        (appointment_id,),
    )
    return cur.fetchone()


def _fetch_current_gfr_sources(cur: Any, appointment_id: int) -> list[dict[str, Any]]:
    """Берёт все СКФ текущего приёма, по которым есть категория ХБП."""
    cur.execute(
        """
        SELECT
            cm.id,
            COALESCE(cm.investigation_date, a.appointment_date::date) AS investigation_date,
            cm.ckd_stage AS category,
            'current_appointment' AS source_type
        FROM calculated_metrics cm
        JOIN appointments a ON a.id = cm.appointment_id
        WHERE cm.appointment_id = %s
          AND cm.ckd_stage IS NOT NULL
        ORDER BY COALESCE(cm.investigation_date, a.appointment_date::date) ASC, cm.id ASC
        """,
        (appointment_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def _fetch_current_albuminuria_sources(cur: Any, appointment_id: int) -> list[dict[str, Any]]:
    """Берёт все альбуминурии текущего приёма, по которым есть A-категория."""
    cur.execute(
        """
        SELECT
            ar.id,
            ar.investigation_date,
            ar.albuminuria_category AS category,
            'current_appointment' AS source_type
        FROM albuminuria_results ar
        WHERE ar.appointment_id = %s
          AND ar.albuminuria_category IS NOT NULL
          AND ar.investigation_date IS NOT NULL
        ORDER BY ar.investigation_date ASC, ar.id ASC
        """,
        (appointment_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def _fetch_latest_previous_gfr_source(
    cur: Any,
    patient_id: int,
    before_or_on: date,
    current_appointment_id: int,
):
    """Берёт последнюю СКФ пациента до даты второго показателя."""
    cur.execute(
        """
        SELECT
            cm.id,
            COALESCE(cm.investigation_date, a.appointment_date::date) AS investigation_date,
            cm.ckd_stage AS category,
            'previous_appointment' AS source_type
        FROM calculated_metrics cm
        JOIN appointments a ON a.id = cm.appointment_id
        WHERE a.patient_id = %s
          AND a.id <> %s
          AND cm.ckd_stage IS NOT NULL
          AND COALESCE(cm.investigation_date, a.appointment_date::date) <= %s
        ORDER BY COALESCE(cm.investigation_date, a.appointment_date::date) DESC, cm.id DESC
        LIMIT 1
        """,
        (patient_id, current_appointment_id, before_or_on),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _fetch_latest_previous_albuminuria_source(
    cur: Any,
    patient_id: int,
    before_or_on: date,
    current_appointment_id: int,
):
    """Берёт последнюю альбуминурию пациента до даты второго показателя."""
    cur.execute(
        """
        SELECT
            ar.id,
            ar.investigation_date,
            ar.albuminuria_category AS category,
            'previous_appointment' AS source_type
        FROM albuminuria_results ar
        JOIN appointments a ON a.id = ar.appointment_id
        WHERE a.patient_id = %s
          AND a.id <> %s
          AND ar.albuminuria_category IS NOT NULL
          AND ar.investigation_date IS NOT NULL
          AND ar.investigation_date <= %s
        ORDER BY ar.investigation_date DESC, ar.id DESC
        LIMIT 1
        """,
        (patient_id, current_appointment_id, before_or_on),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _build_pair_assessment(
    appointment_id: int,
    appointment_date: date,
    gfr_source: dict[str, Any],
    albuminuria_source: dict[str, Any],
    display_order: int,
) -> dict[str, Any] | None:
    """Создаёт одну рассчитанную строку KDIGO, если источники валидны."""
    gfr_category = normalize_ckd_stage_for_storage(gfr_source.get("category"))
    albuminuria_category = normalize_albuminuria_category(albuminuria_source.get("category"))
    risk = calculate_kdigo_risk(gfr_category, albuminuria_category)
    if risk.get("status") != "calculated":
        return None

    interval_days = source_interval_days(
        gfr_source.get("investigation_date"),
        albuminuria_source.get("investigation_date"),
    )
    if not is_interval_allowed(risk.get("prognosis_level"), interval_days):
        return None

    assessment = {
        "appointment_id": appointment_id,
        "assessment_date": appointment_date,
        "gfr_metric_id": gfr_source.get("id"),
        "gfr_investigation_date": gfr_source.get("investigation_date"),
        "gfr_category": risk["gfr_category"],
        "gfr_source_type": gfr_source.get("source_type") or "current_appointment",
        "albuminuria_result_id": albuminuria_source.get("id"),
        "albuminuria_investigation_date": albuminuria_source.get("investigation_date"),
        "albuminuria_category": risk["albuminuria_category"],
        "albuminuria_source_type": albuminuria_source.get("source_type") or "current_appointment",
        "source_interval_days": interval_days,
        "combined_category": risk["combined_category"],
        "prognosis_level": risk["prognosis_level"],
        "prognosis_text": risk["prognosis_text"],
        "calculation_status": "calculated",
        "display_order": display_order,
    }
    assessment["display_text"] = format_risk_phrase(assessment)
    assessment["pair_key"] = build_source_pair_key(
        assessment["gfr_investigation_date"],
        assessment["gfr_category"],
        assessment["albuminuria_investigation_date"],
        assessment["albuminuria_category"],
    )
    return assessment


def _deduplicate_assessments(assessments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Убирает одинаковые пары дат/категорий, сохраняя порядок."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for assessment in assessments:
        key = assessment.get("pair_key")
        if not key or key in seen:
            continue
        seen.add(key)
        assessment["display_order"] = len(result)
        result.append(assessment)
    return result


def build_kdigo_assessments_for_appointment(
    cur: Any,
    appointment_id: int,
    excluded_pairs: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Строит все рассчитанные KDIGO-комбинации для приёма.

    Правила:
    - если в текущем приёме есть и СКФ, и альбуминурия — считаем все текущие
      комбинации СКФ × альбуминурия;
    - если текущая СКФ есть, а альбуминурии нет — берём последнюю подходящую
      альбуминурию из предыдущих приёмов;
    - если текущая альбуминурия есть, а СКФ нет — берём последнюю подходящую
      СКФ из предыдущих приёмов;
    - если оба показателя отсутствуют в текущем приёме — ничего не сохраняем.
    """
    meta = _fetch_appointment_patient_and_date(cur, appointment_id)
    if not meta:
        return []

    patient_id = int(meta["patient_id"])
    appointment_date = meta["appointment_date"]
    current_gfr_sources = _fetch_current_gfr_sources(cur, appointment_id)
    current_albuminuria_sources = _fetch_current_albuminuria_sources(cur, appointment_id)
    excluded_pairs_set = {str(item) for item in (excluded_pairs or []) if item}

    raw_assessments: list[dict[str, Any]] = []

    if current_gfr_sources and current_albuminuria_sources:
        for gfr_source in current_gfr_sources:
            for albuminuria_source in current_albuminuria_sources:
                assessment = _build_pair_assessment(
                    appointment_id,
                    appointment_date,
                    gfr_source,
                    albuminuria_source,
                    display_order=len(raw_assessments),
                )
                if assessment:
                    raw_assessments.append(assessment)

    elif current_gfr_sources and not current_albuminuria_sources:
        for gfr_source in current_gfr_sources:
            gfr_date = gfr_source.get("investigation_date") or appointment_date
            albuminuria_source = _fetch_latest_previous_albuminuria_source(
                cur,
                patient_id,
                gfr_date,
                appointment_id,
            )
            if not albuminuria_source:
                continue
            assessment = _build_pair_assessment(
                appointment_id,
                appointment_date,
                gfr_source,
                albuminuria_source,
                display_order=len(raw_assessments),
            )
            if assessment:
                raw_assessments.append(assessment)

    elif current_albuminuria_sources and not current_gfr_sources:
        for albuminuria_source in current_albuminuria_sources:
            albuminuria_date = albuminuria_source.get("investigation_date") or appointment_date
            gfr_source = _fetch_latest_previous_gfr_source(
                cur,
                patient_id,
                albuminuria_date,
                appointment_id,
            )
            if not gfr_source:
                continue
            assessment = _build_pair_assessment(
                appointment_id,
                appointment_date,
                gfr_source,
                albuminuria_source,
                display_order=len(raw_assessments),
            )
            if assessment:
                raw_assessments.append(assessment)

    assessments = _deduplicate_assessments(raw_assessments)
    if excluded_pairs_set:
        assessments = [
            item for item in assessments if item.get("pair_key") not in excluded_pairs_set
        ]
        for index, item in enumerate(assessments):
            item["display_order"] = index
    return assessments


def _insert_kdigo_assessment(cur: Any, assessment: dict[str, Any]):
    """Сохраняет одну рассчитанную KDIGO-комбинацию."""
    cur.execute(
        """
        INSERT INTO ckd_prognosis_results (
            appointment_id,
            assessment_date,
            gfr_metric_id,
            albuminuria_result_id,
            gfr_investigation_date,
            albuminuria_investigation_date,
            gfr_source_type,
            albuminuria_source_type,
            source_interval_days,
            calculation_status,
            display_order,
            is_active,
            gfr_category,
            albuminuria_category,
            combined_category,
            prognosis_level,
            prognosis_text,
            created_at,
            updated_at
        ) VALUES (
            %(appointment_id)s,
            %(assessment_date)s,
            %(gfr_metric_id)s,
            %(albuminuria_result_id)s,
            %(gfr_investigation_date)s,
            %(albuminuria_investigation_date)s,
            %(gfr_source_type)s,
            %(albuminuria_source_type)s,
            %(source_interval_days)s,
            %(calculation_status)s,
            %(display_order)s,
            TRUE,
            %(gfr_category)s,
            %(albuminuria_category)s,
            %(combined_category)s,
            %(prognosis_level)s,
            %(prognosis_text)s,
            NOW(),
            NOW()
        )
        ON CONFLICT (appointment_id, gfr_metric_id, albuminuria_result_id)
        WHERE is_active = true AND calculation_status = 'calculated'
        DO UPDATE SET
            assessment_date = EXCLUDED.assessment_date,
            gfr_investigation_date = EXCLUDED.gfr_investigation_date,
            albuminuria_investigation_date = EXCLUDED.albuminuria_investigation_date,
            gfr_source_type = EXCLUDED.gfr_source_type,
            albuminuria_source_type = EXCLUDED.albuminuria_source_type,
            source_interval_days = EXCLUDED.source_interval_days,
            display_order = EXCLUDED.display_order,
            gfr_category = EXCLUDED.gfr_category,
            albuminuria_category = EXCLUDED.albuminuria_category,
            combined_category = EXCLUDED.combined_category,
            prognosis_level = EXCLUDED.prognosis_level,
            prognosis_text = EXCLUDED.prognosis_text,
            updated_at = NOW()
        RETURNING *
        """,
        assessment,
    )
    return cur.fetchone()


def save_ckd_prognosis_for_appointment(
    appointment_id: int,
    cur: Any | None = None,
    excluded_pairs: Iterable[str] | None = None,
):
    """
    Пересчитывает и сохраняет KDIGO-риск для приёма.

    Возвращает список сохранённых строк. Если данных недостаточно или второй
    показатель устарел, список будет пустым: в базе не создаётся фиктивный
    риск без строгих источников.
    """

    def _save(cursor: Any):
        assessments = build_kdigo_assessments_for_appointment(
            cursor,
            appointment_id,
            excluded_pairs=excluded_pairs,
        )

        cursor.execute(
            """
            DELETE FROM ckd_prognosis_results
            WHERE appointment_id = %s
              AND calculation_status = 'calculated'
            """,
            (appointment_id,),
        )

        saved_rows = []
        for assessment in assessments:
            saved_rows.append(_insert_kdigo_assessment(cursor, assessment))
        return saved_rows

    if cur is not None:
        return _save(cur)

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            return _save(cursor)


def recalculate_ckd_prognosis_for_appointment(appointment_id: int, assessment_date=None):
    """
    Публичная функция пересчёта одного приёма.

    assessment_date оставлен для совместимости со старым кодом и больше не
    используется как дата источника: источники берутся из calculated_metrics и
    albuminuria_results.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return save_ckd_prognosis_for_appointment(appointment_id, cur=cur)


def hide_ckd_prognosis_result(result_id: int, hidden_reason: str | None = None):
    """Помечает сохранённую строку KDIGO как скрытую врачом."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ckd_prognosis_results
                SET is_active = FALSE,
                    calculation_status = 'doctor_removed',
                    hidden_at = NOW(),
                    hidden_reason = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (hidden_reason, result_id),
            )
            return cur.fetchone()


def _fetch_appointment_ckd_prognosis(cur: Any, appointment_id: int):
    """Возвращает первую активную строку KDIGO выбранного приёма."""
    cur.execute(
        """
        SELECT
            id,
            appointment_id,
            assessment_date,
            gfr_metric_id,
            albuminuria_result_id,
            gfr_investigation_date,
            albuminuria_investigation_date,
            gfr_source_type,
            albuminuria_source_type,
            source_interval_days,
            calculation_status,
            display_order,
            is_active,
            gfr_category,
            albuminuria_category,
            combined_category,
            prognosis_level,
            prognosis_text,
            (
                'По KDIGO: ' || combined_category || ' — ' || prognosis_text ||
                ' прогрессирования ХБП и развития ХПН (рассчитано по СКФ от ' ||
                to_char(gfr_investigation_date, 'DD.MM.YYYY') ||
                ', альбуминурия от ' ||
                to_char(albuminuria_investigation_date, 'DD.MM.YYYY') || ')'
            ) AS display_text
        FROM ckd_prognosis_results
        WHERE appointment_id = %s
          AND is_active = TRUE
          AND calculation_status = 'calculated'
        ORDER BY display_order ASC, id ASC
        LIMIT 1
        """,
        (appointment_id,),
    )
    return cur.fetchone()


def _fetch_appointment_ckd_prognosis_results(cur: Any, appointment_id: int):
    """Возвращает все активные KDIGO-строки выбранного приёма."""
    cur.execute(
        """
        SELECT
            id,
            appointment_id,
            assessment_date,
            gfr_metric_id,
            albuminuria_result_id,
            gfr_investigation_date,
            albuminuria_investigation_date,
            gfr_source_type,
            albuminuria_source_type,
            source_interval_days,
            calculation_status,
            display_order,
            is_active,
            gfr_category,
            albuminuria_category,
            combined_category,
            prognosis_level,
            prognosis_text,
            (
                'По KDIGO: ' || combined_category || ' — ' || prognosis_text ||
                ' прогрессирования ХБП и развития ХПН (рассчитано по СКФ от ' ||
                to_char(gfr_investigation_date, 'DD.MM.YYYY') ||
                ', альбуминурия от ' ||
                to_char(albuminuria_investigation_date, 'DD.MM.YYYY') || ')'
            ) AS display_text
        FROM ckd_prognosis_results
        WHERE appointment_id = %s
          AND is_active = TRUE
          AND calculation_status = 'calculated'
        ORDER BY display_order ASC, id ASC
        """,
        (appointment_id,),
    )
    return cur.fetchall()


def get_appointment_ckd_prognosis(appointment_id: int):
    """Возвращает первую активную KDIGO-строку для конкретного приёма."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_appointment_ckd_prognosis(cur, appointment_id)


def get_appointment_ckd_prognosis_results(appointment_id: int):
    """Возвращает все активные KDIGO-строки для конкретного приёма."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_appointment_ckd_prognosis_results(cur, appointment_id)


def _fetch_patient_ckd_prognosis_history(cur: Any, patient_id: int, until_date=None):
    """Возвращает историю всех активных KDIGO-строк пациента."""
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
            cpr.gfr_metric_id,
            cpr.albuminuria_result_id,
            cpr.gfr_investigation_date,
            cpr.albuminuria_investigation_date,
            cpr.gfr_source_type,
            cpr.albuminuria_source_type,
            cpr.source_interval_days,
            cpr.calculation_status,
            cpr.display_order,
            cpr.is_active,
            cpr.gfr_category,
            cpr.albuminuria_category,
            cpr.combined_category,
            cpr.prognosis_level,
            cpr.prognosis_text,
            (
                'По KDIGO: ' || cpr.combined_category || ' — ' || cpr.prognosis_text ||
                ' прогрессирования ХБП и развития ХПН (рассчитано по СКФ от ' ||
                to_char(cpr.gfr_investigation_date, 'DD.MM.YYYY') ||
                ', альбуминурия от ' ||
                to_char(cpr.albuminuria_investigation_date, 'DD.MM.YYYY') || ')'
            ) AS display_text
        FROM ckd_prognosis_results cpr
        JOIN appointments a ON cpr.appointment_id = a.id
        WHERE a.patient_id = %s
          AND cpr.is_active = TRUE
          AND cpr.calculation_status = 'calculated'
          {date_filter}
        ORDER BY
            cpr.assessment_date ASC,
            cpr.gfr_investigation_date ASC,
            cpr.albuminuria_investigation_date ASC,
            cpr.display_order ASC,
            cpr.id ASC
        """,
        params,
    )
    return cur.fetchall()


def get_patient_ckd_prognosis_history(patient_id: int, until_date=None):
    """Возвращает историю активных KDIGO-строк пациента."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_patient_ckd_prognosis_history(cur, patient_id, until_date)
