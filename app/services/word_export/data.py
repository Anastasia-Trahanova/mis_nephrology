"""
Сбор данных для Word-заключения.

Получает выбранный приём, определяет его тип, загружает место приёма,
диагнозы, назначения и историю исследований до даты выбранного приёма.
"""

from __future__ import annotations

from app.repositories.appointments import (
    get_appointment_diet,
    get_appointment_full_data,
    get_appointment_medications,
    get_patient_appointments,
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

from .formatting import value_with_unit


def prepare_albuminuria_records(records):
    """Добавляет отображаемые значения вместе с исходными единицами измерения."""
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



def _visit_kind(appointments, appointment_id: int) -> str:
    """Повторяет логику ЭМК: самый ранний приём первичный, остальные повторные."""
    appointments = list(appointments or [])
    if appointments and appointments[-1].get("appointment_id") == appointment_id:
        return "первичный"
    return "повторный"


def get_word_export_context(appointment_id: int) -> dict | None:
    appointment = get_appointment_full_data(appointment_id)
    if not appointment:
        return None

    patient_id = appointment.get("patient_id")
    appointments = get_patient_appointments(patient_id)

    until_date = None
    if appointment.get("appointment_date"):
        until_date = appointment["appointment_date"].date()

    location_info = None
    if appointment.get("location_id"):
        location_info = get_location_info(appointment["location_id"])

    return {
        "appointment": appointment,
        "visit_kind": _visit_kind(appointments, appointment_id),
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
    }
