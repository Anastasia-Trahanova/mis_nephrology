"""
Роуты создания новых приёмов существующих пациентов.

Как работает:
- принимает POST-форму повторного приёма;
- берёт текущего врача из сессии;
- до сохранения читает последний приём пациента, чтобы потом понять, какие
  предзаполненные поля врач изменил или удалил;
- передаёт сохранение в patient_appointment_service;
- после успешного сохранения пишет основное событие audit_events;
- после основного события пишет подробности audit_event_changes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.repositories.appointments import (
    get_appointment_medications,
    get_last_appointment_data,
)
from app.repositories.diagnoses import get_appointment_icd10_diagnoses
from app.repositories.audit_log import log_audit_changes, log_audit_event
from app.security.permissions import require_doctor_with_id
from app.services.audit_details import build_appointment_medical_audit_changes
from app.services.patient_appointment_service import create_appointment_for_existing_patient


router = APIRouter(tags=["appointments"])


def _audit_form_with_session_doctor(form: Any, current_doctor_id: int) -> dict[str, Any]:
    """Копирует форму для audit и принудительно ставит врача из сессии."""
    result: dict[str, Any] = {}
    for key in form.keys():
        values = form.getlist(key)
        result[key] = values if len(values) > 1 else form.get(key)
    result["doctor_id"] = str(current_doctor_id)
    return result


@router.post("/api/patients/{patient_id}/appointments/new")
async def create_new_appointment_for_existing_patient(patient_id: int, request: Request):
    """Создаёт новый приём для уже существующего пациента."""
    current_doctor_id = require_doctor_with_id(request)
    form = await request.form()

    previous_appointment = get_last_appointment_data(patient_id)
    previous_medications = []
    previous_icd10_diagnoses = []

    if previous_appointment and previous_appointment.get("appointment_id"):
        previous_appointment_id = previous_appointment["appointment_id"]
        previous_medications = get_appointment_medications(previous_appointment_id)
        previous_icd10_diagnoses = get_appointment_icd10_diagnoses(previous_appointment_id)

    try:
        result = create_appointment_for_existing_patient(
            patient_id,
            form,
            current_doctor_id=current_doctor_id,
        )
    except Exception as exc:
        log_audit_event(
            request,
            "save_error",
            result="error",
            patient_id=patient_id,
            entity_type="appointment",
            details="ошибка создания повторного приёма",
            error_message=repr(exc),
        )
        raise

    event_id = log_audit_event(
        request,
        "create_appointment",
        patient_id=result.patient_id,
        appointment_id=result.appointment_id,
        entity_type="appointment",
        entity_id=result.appointment_id,
        details="создан повторный приём",
    )

    audit_form = _audit_form_with_session_doctor(form, current_doctor_id)
    log_audit_changes(
        event_id,
        build_appointment_medical_audit_changes(
            audit_form,
            previous_appointment=previous_appointment,
            previous_medications=previous_medications,
            previous_icd10_diagnoses=previous_icd10_diagnoses,
            appointment_id=result.appointment_id,
        ),
    )

    return RedirectResponse(
        url=f"/patient/{result.patient_id}?appointment_id={result.appointment_id}",
        status_code=303,
    )
