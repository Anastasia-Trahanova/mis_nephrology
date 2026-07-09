"""
Роуты создания нового пациента.

Как работает:
- принимает POST-форму нового пациента;
- берёт текущего врача из сессии;
- передаёт сохранение в patient_appointment_service;
- после успешного создания пишет основное событие audit_events;
- после основного события пишет подробности audit_event_changes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.repositories.audit_log import log_audit_changes, log_audit_event
from app.security.permissions import require_doctor_with_id
from app.services.audit_details import build_patient_creation_audit_changes
from app.services.patient_appointment_service import create_patient_with_first_appointment


router = APIRouter(tags=["patients"])


def _audit_form_with_session_doctor(form: Any, current_doctor_id: int) -> dict[str, Any]:
    """Копирует форму для audit и принудительно ставит врача из сессии."""
    result: dict[str, Any] = {}
    for key in form.keys():
        values = form.getlist(key)
        result[key] = values if len(values) > 1 else form.get(key)
    result["doctor_id"] = str(current_doctor_id)
    return result


@router.post("/api/patients/new")
async def create_new_patient(request: Request):
    """Создаёт нового пациента и первый приём."""
    current_doctor_id = require_doctor_with_id(request)
    form = await request.form()

    try:
        result = create_patient_with_first_appointment(
            form,
            current_doctor_id=current_doctor_id,
        )
    except Exception as exc:
        log_audit_event(
            request,
            "save_error",
            result="error",
            entity_type="patient",
            details="ошибка создания нового пациента",
            error_message=repr(exc),
        )
        raise

    event_id = log_audit_event(
        request,
        "create_patient",
        patient_id=result.patient_id,
        appointment_id=result.appointment_id,
        entity_type="patient",
        entity_id=result.patient_id,
        details="создан новый пациент и первый приём",
    )

    audit_form = _audit_form_with_session_doctor(form, current_doctor_id)
    log_audit_changes(
        event_id,
        build_patient_creation_audit_changes(
            audit_form,
            patient_id=result.patient_id,
            appointment_id=result.appointment_id,
        ),
    )

    return RedirectResponse(
        url=f"/patient/{result.patient_id}?appointment_id={result.appointment_id}",
        status_code=303,
    )
