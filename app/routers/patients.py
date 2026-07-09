"""
Роуты создания нового пациента.

Как работает:
- принимает POST-форму нового пациента;
- передаёт сохранение в patient_appointment_service;
- после успешного создания пишет основное событие audit_events;
- после основного события пишет подробности audit_event_changes: данные пациента,
  первый приём, добавленные анализы, МКБ-10, KDIGO, рекомендации и лекарства;
- при ошибке сохранения пишет безопасное событие ошибки без текста медицинских полей.

Что редактировать здесь:
- URL создания нового пациента;
- состав audit-событий create_patient/save_error;
- подключение build_patient_creation_audit_changes, если меняется логика формы.

Что не редактировать здесь:
- SQL создания пациента;
- расчёты СКФ/KDIGO;
- HTML формы нового пациента.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.repositories.audit_log import log_audit_changes, log_audit_event
from app.services.audit_details import build_patient_creation_audit_changes
from app.services.patient_appointment_service import create_patient_with_first_appointment


router = APIRouter(tags=["patients"])


@router.post("/api/patients/new")
async def create_new_patient(request: Request):
    """Создаёт нового пациента и первый приём."""
    form = await request.form()
    try:
        result = create_patient_with_first_appointment(form)
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
    log_audit_changes(
        event_id,
        build_patient_creation_audit_changes(
            form,
            patient_id=result.patient_id,
            appointment_id=result.appointment_id,
        ),
    )

    return RedirectResponse(
        url=f"/patient/{result.patient_id}?appointment_id={result.appointment_id}",
        status_code=303,
    )
