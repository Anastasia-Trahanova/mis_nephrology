"""
Назначение файла: сборка context для форм нового пациента и повторного приёма.

Что делает этот файл:
- get_new_patient_context() собирает справочники для страницы добавления нового пациента;
- get_new_appointment_context(patient_id) собирает пациента, последний приём, истории анализов и справочники для повторного приёма;
- подготавливает данные прошлой СКФ и прошлой альбуминурии для live-блока KDIGO;
- подготавливает матрицу истории прогнозов KDIGO для раскрывающегося блока в форме повторного приёма;
- не содержит SQL напрямую: все чтения идут через функции из app.repositories.

Как это работает:
- repository-функции получают данные из PostgreSQL;
- этот service собирает их в один словарь context для Jinja-шаблона;
- JavaScript в app/static/js/kdigo_risk_preview.js читает kdigo_previous_gfr_data и kdigo_previous_albuminuria_data из JSON в шаблоне.

Что можно редактировать:
- какие справочники и истории передаются в форму;
- какие прошлые данные доступны для fallback-расчёта KDIGO;
- состав context для Jinja.

Что не редактировать здесь:
- SQL-запросы;
- внешний вид формы;
- сохранение приёма;
- медицинскую матрицу риска KDIGO.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.db.connection import get_db_connection
from app.repositories.appointments import (
    _fetch_appointment_diet,
    _fetch_appointment_medications,
    _fetch_last_appointment_data,
    _fetch_patient_appointments,
)
from app.repositories.ckd_prognosis import _fetch_patient_ckd_prognosis_history
from app.repositories.lab_history import (
    _fetch_patient_albuminuria_history,
    _fetch_patient_biochemistry_history,
    _fetch_patient_cbc_history,
    _fetch_patient_metrics_history,
    _fetch_patient_ultrasound_history,
    _fetch_patient_urinalysis_history,
)
from app.repositories.patients import _fetch_patient_by_id
from app.repositories.reference_data import (
    _fetch_appointment_icd10_diagnoses,
    _fetch_branches,
    _fetch_doctors,
    _fetch_icd10_diagnoses,
    _fetch_locations_by_branch,
    _fetch_medications_dictionary,
)
from app.services.kdigo_risk_matrix_service import build_kdigo_risk_matrix


def _group_icd10_diagnoses_for_form(icd10_diagnoses):
    """Группирует МКБ-10 диагнозы для подстановки в форму повторного приёма."""
    result = {
        "main": None,
        "complications": [],
        "comorbidities": [],
    }

    for item in icd10_diagnoses:
        if item["diagnosis_type"] == "main" and result["main"] is None:
            result["main"] = item
        elif item["diagnosis_type"] == "complication":
            result["complications"].append(item)
        elif item["diagnosis_type"] == "comorbidity":
            result["comorbidities"].append(item)

    return result


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    """Читает поле из dict/RealDictRow/объекта."""
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        return getattr(row, key, default)


def _date_to_iso(value: Any) -> str | None:
    """Готовит дату для JSON, который читает JavaScript формы."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text[:10] if text else None


def _prepare_kdigo_previous_gfr_data(metrics_history) -> list[dict[str, str]]:
    """Готовит историю СКФ для fallback-расчёта KDIGO в форме повторного приёма."""
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for item in metrics_history or []:
        current_date = _date_to_iso(_row_get(item, "investigation_date"))
        category = _row_get(item, "ckd_stage")
        if not current_date or not category:
            continue

        key = (current_date, str(category))
        if key in seen:
            continue
        seen.add(key)
        result.append({"date": current_date, "category": str(category)})

    return result


def _prepare_kdigo_previous_albuminuria_data(albuminuria_history) -> list[dict[str, str]]:
    """Готовит историю альбуминурии для fallback-расчёта KDIGO в форме повторного приёма."""
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for item in albuminuria_history or []:
        current_date = _date_to_iso(_row_get(item, "investigation_date"))
        category = _row_get(item, "albuminuria_category")
        if not current_date or not category:
            continue

        key = (current_date, str(category))
        if key in seen:
            continue
        seen.add(key)
        result.append({"date": current_date, "category": str(category)})

    return result


def get_new_appointment_context(patient_id: int):
    """Собирает данные для формы нового приёма существующего пациента одним соединением к БД."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            patient = _fetch_patient_by_id(cur, patient_id)
            if not patient:
                return None

            appointments = _fetch_patient_appointments(cur, patient_id)
            last_appointment = _fetch_last_appointment_data(cur, patient_id)
            last_appointment_id = appointments[0]["appointment_id"] if appointments else None

            last_icd10_diagnoses = []
            last_icd10_diagnoses_grouped = {
                "main": None,
                "complications": [],
                "comorbidities": [],
            }
            if last_appointment_id:
                last_icd10_diagnoses = _fetch_appointment_icd10_diagnoses(cur, last_appointment_id)
                last_icd10_diagnoses_grouped = _group_icd10_diagnoses_for_form(last_icd10_diagnoses)

            metrics_history = _fetch_patient_metrics_history(cur, patient_id)
            albuminuria_history = _fetch_patient_albuminuria_history(cur, patient_id)
            kdigo_previous_history = _fetch_patient_ckd_prognosis_history(cur, patient_id)

            return {
                "patient": patient,
                "appointments": appointments,
                "branches": _fetch_branches(cur),
                "doctors": _fetch_doctors(cur),
                "locations": _fetch_locations_by_branch(cur),
                "last_appointment": last_appointment,
                "last_icd10_diagnoses": last_icd10_diagnoses,
                "last_icd10_diagnoses_grouped": last_icd10_diagnoses_grouped,
                "last_medications": _fetch_appointment_medications(cur, last_appointment_id) if last_appointment_id else [],
                "last_diet_info": _fetch_appointment_diet(cur, last_appointment_id) if last_appointment_id else None,
                "cbc_history": _fetch_patient_cbc_history(cur, patient_id),
                "biochemistry_history": _fetch_patient_biochemistry_history(cur, patient_id),
                "urinalysis_history": _fetch_patient_urinalysis_history(cur, patient_id),
                "albuminuria_history": albuminuria_history,
                "ultrasound_history": _fetch_patient_ultrasound_history(cur, patient_id),
                "metrics_history": metrics_history,
                "icd10_diagnoses": _fetch_icd10_diagnoses(cur),
                "medications_dictionary": _fetch_medications_dictionary(cur),
                "kdigo_previous_gfr_data": _prepare_kdigo_previous_gfr_data(metrics_history),
                "kdigo_previous_albuminuria_data": _prepare_kdigo_previous_albuminuria_data(albuminuria_history),
                "kdigo_previous_history_matrix": build_kdigo_risk_matrix(kdigo_previous_history),
            }


def get_new_patient_context():
    """Собирает данные для формы нового пациента одним соединением к БД."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return {
                "branches": _fetch_branches(cur),
                "doctors": _fetch_doctors(cur),
                "locations": _fetch_locations_by_branch(cur),
                "icd10_diagnoses": _fetch_icd10_diagnoses(cur),
                "medications_dictionary": _fetch_medications_dictionary(cur),
                "kdigo_previous_gfr_data": [],
                "kdigo_previous_albuminuria_data": [],
                "kdigo_previous_history_matrix": build_kdigo_risk_matrix([]),
            }
