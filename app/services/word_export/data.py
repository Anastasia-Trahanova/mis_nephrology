"""
Назначение файла: сбор данных для Word-заключения.

Что выполняет файл:
- получает данные приёма, пациента, назначений, диеты и историй анализов;
- подготавливает display-поля для альбуминурии и KDIGO;
- не создаёт Document и не управляет внешним видом Word-файла.
"""

from __future__ import annotations

from app.repositories.appointments import (
    get_appointment_diet,
    get_appointment_full_data,
    get_appointment_medications,
)
from app.repositories.ckd_prognosis import (
    get_appointment_ckd_prognosis,
    get_patient_ckd_prognosis_history,
)
from app.repositories.diagnoses import get_appointment_icd10_diagnoses
from app.repositories.lab_history import (
    get_patient_albuminuria_history,
    get_patient_biochemistry_history,
    get_patient_cbc_history,
    get_patient_metrics_history,
    get_patient_ultrasound_history,
    get_patient_urinalysis_history,
)
from app.repositories.reference_data import get_location_info

from .formatting import prognosis_display, value_with_unit


def prepare_albuminuria_records(records):
    """Добавляет поля для красивого вывода альбуминурии в Word."""
    prepared = []
    for record in records or []:
        item = dict(record)
        item["urine_albumin_display"] = value_with_unit(
            item.get("urine_albumin"),
            item.get("urine_albumin_unit"),
        )
        item["urine_creatinine_display"] = value_with_unit(
            item.get("urine_creatinine"),
            item.get("urine_creatinine_unit"),
        )
        prepared.append(item)
    return prepared


def prepare_ckd_prognosis_records(records):
    """Добавляет поле prognosis_display для компактного вывода прогноза ХБП."""
    prepared = []
    for record in records or []:
        item = dict(record)
        item["prognosis_display"] = prognosis_display(item)
        prepared.append(item)
    return prepared


def get_word_export_context(appointment_id: int) -> dict | None:
    """Собирает все данные, необходимые для Word-экспорта."""
    appointment = get_appointment_full_data(appointment_id)
    if not appointment:
        return None

    patient_id = appointment.get("patient_id")
    until_date = None
    if appointment.get("appointment_date"):
        until_date = appointment["appointment_date"].date()

    location_info = None
    if appointment.get("location_id"):
        location_info = get_location_info(appointment["location_id"])

    return {
        "appointment": appointment,
        "medications": get_appointment_medications(appointment_id),
        "diet_info": get_appointment_diet(appointment_id),
        "diagnoses": get_appointment_icd10_diagnoses(appointment_id),
        "location_info": location_info,
        "labs": {
            "cbc_history": get_patient_cbc_history(patient_id, until_date),
            "biochemistry_history": get_patient_biochemistry_history(patient_id, until_date),
            "urinalysis_history": get_patient_urinalysis_history(patient_id, until_date),
            "metrics_history": get_patient_metrics_history(patient_id, until_date),
            "albuminuria_history": prepare_albuminuria_records(
                get_patient_albuminuria_history(patient_id, until_date)
            ),
            "ultrasound_history": get_patient_ultrasound_history(patient_id, until_date),
        },
        "kdigo": {
            "history": prepare_ckd_prognosis_records(
                get_patient_ckd_prognosis_history(patient_id, until_date)
            ),
            "current": get_appointment_ckd_prognosis(appointment_id),
        },
    }
