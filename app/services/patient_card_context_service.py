"""
Назначение файла: сборка context для карточки пациента.

Этот сервис не содержит SQL напрямую. Он собирает данные из repository-функций
и формирует единый словарь для шаблона patient_card.html.

Что выполняет файл:
- загружает пациента;
- загружает список приёмов пациента;
- выбирает текущий/предыдущий приём для отображения;
- загружает лекарства, диету, МКБ-10 диагнозы выбранного приёма;
- загружает истории анализов и прогнозов до даты выбранного приёма;
- возвращает совместимый context для существующего шаблона.

Что редактировать здесь:
- какие блоки данных показываются в карточке пациента;
- какие истории загружаются для карточки;
- логику выбора selected_appointment.

Что не редактировать здесь:
- SQL-тексты — они в app/repositories;
- внешний вид карточки — он в app/templates/patient_card;
- сохранение данных формы.
"""

from __future__ import annotations

from app.db.connection import get_db_connection
from app.repositories.appointments import (
    _fetch_appointment_diet,
    _fetch_appointment_full_data,
    _fetch_appointment_medications,
    _fetch_patient_appointments,
)
from app.repositories.ckd_prognosis import (
    _fetch_appointment_ckd_prognosis,
    _fetch_patient_ckd_prognosis_history,
)
from app.repositories.lab_history import (
    _fetch_patient_albuminuria_history,
    _fetch_patient_biochemistry_history,
    _fetch_patient_cbc_history,
    _fetch_patient_metrics_history,
    _fetch_patient_ultrasound_history,
    _fetch_patient_urinalysis_history,
)
from app.repositories.patients import _fetch_patient_by_id
from app.repositories.reference_data import _fetch_appointment_icd10_diagnoses


def get_patient_card_context(
    patient_id: int,
    selected_appointment_id: int | None = None,
    show_previous_labs: bool = False,
    show_form: bool = False,
):
    """Собирает context карточки пациента одним соединением к БД."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            patient = _fetch_patient_by_id(cur, patient_id)
            if not patient:
                return None

            appointments = _fetch_patient_appointments(cur, patient_id)

            appointment_data = None
            if show_previous_labs and appointments and len(appointments) > 1:
                prev_appointment_id = appointments[1]["appointment_id"]
                appointment_data = _fetch_appointment_full_data(cur, prev_appointment_id)
                if appointment_data:
                    appointment_data["is_previous_labs"] = True
                    appointment_data["previous_labs_date"] = appointment_data.get("appointment_date")

            if not selected_appointment_id and appointments and not show_form:
                selected_appointment_id = appointments[0]["appointment_id"]

            medications = []
            diet_info = None
            icd10_diagnoses = []

            if selected_appointment_id and not appointment_data:
                appointment_data = _fetch_appointment_full_data(cur, int(selected_appointment_id))

                if appointment_data and appointment_data.get("patient_id") != patient_id:
                    return {"patient": patient, "forbidden": True}

                if appointment_data:
                    medications = _fetch_appointment_medications(cur, int(selected_appointment_id))
                    diet_info = _fetch_appointment_diet(cur, int(selected_appointment_id))
                    icd10_diagnoses = _fetch_appointment_icd10_diagnoses(cur, int(selected_appointment_id))

            until_date = None
            if not show_form and appointment_data and appointment_data.get("appointment_date"):
                until_date = appointment_data["appointment_date"].date()

            return {
                "patient": patient,
                "appointments": appointments,
                "selected_appointment": appointment_data,
                "medications": medications,
                "diet_info": diet_info,
                "icd10_diagnoses": icd10_diagnoses,
                "biochemistry_history": _fetch_patient_biochemistry_history(cur, patient_id, until_date),
                "cbc_history": _fetch_patient_cbc_history(cur, patient_id, until_date),
                "urinalysis_history": _fetch_patient_urinalysis_history(cur, patient_id, until_date),
                "metrics_history": _fetch_patient_metrics_history(cur, patient_id, until_date),
                "ultrasound_history": _fetch_patient_ultrasound_history(cur, patient_id, until_date),
                "albuminuria_history": _fetch_patient_albuminuria_history(cur, patient_id, until_date),
                "ckd_prognosis_current": _fetch_appointment_ckd_prognosis(cur, int(selected_appointment_id)) if selected_appointment_id else None,
                "ckd_prognosis_history": _fetch_patient_ckd_prognosis_history(cur, patient_id, until_date),
                # Ключи ниже оставлены для совместимости с шаблонами/старым кодом.
                # В обычной карточке они не создают дополнительные запросы.
                "branches": [],
                "doctors": [],
                "locations": [],
                "last_appointment": None,
                "last_medications": [],
                "last_diet_info": None,
                "location_info": None,
            }
