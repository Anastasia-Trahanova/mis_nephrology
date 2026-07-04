"""
Бизнес-операции создания пациента и приёма.

Этот модуль нужен, чтобы роутеры были тонкими:
- роутер получает request.form();
- вызывает одну функцию сервиса;
- делает redirect.

Здесь находится транзакционная логика:
- создать нового пациента и первый приём;
- создать новый приём существующему пациенту;
- вызвать сохранение всех разделов приёма;
- commit / rollback.

SQL создания patients и appointments вынесен в repositories:
- app/repositories/patients.py;
- app/repositories/appointments.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from ..database import get_db_connection
from ..repositories.appointments import create_appointment
from ..repositories.patients import create_patient, get_patient_for_appointment
from ..validation import validate_appointment_form
from .appointment_form_parser import (
    parse_appointment_form,
    parse_new_patient_form,
    parse_required_appointment_fields,
)
from .appointment_save_service import save_appointment_details


@dataclass(frozen=True)
class AppointmentSaveResult:
    """Результат создания пациента/приёма для дальнейшего redirect."""

    patient_id: int
    appointment_id: int


def _raise_validation_errors(validation_errors: list[dict[str, Any]] | dict[str, Any]) -> None:
    """Приводит ошибки медицинской валидации к текущему формату HTTPException."""
    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Форма содержит некорректные медицинские значения",
                "errors": validation_errors,
            },
        )


def create_patient_with_first_appointment(form: Any) -> AppointmentSaveResult:
    """
    Создаёт нового пациента и его первый приём.

    Используется POST /api/patients/new.
    """
    patient_data = parse_new_patient_form(form)
    appointment_required = parse_required_appointment_fields(form)
    appointment_datetime = appointment_required["appointment_datetime"]

    validation_errors = validate_appointment_form(form, appointment_datetime.date())
    _raise_validation_errors(validation_errors)

    appointment_data = parse_appointment_form(form, appointment_datetime)

    with get_db_connection() as conn:
        try:
            with conn.cursor() as cur:
                patient_id = create_patient(cur, patient_data)
                appointment_id = create_appointment(
                    cur=cur,
                    patient_id=patient_id,
                    doctor_id=appointment_required["doctor_id"],
                    location_id=appointment_required["location_id"],
                    appointment_datetime=appointment_datetime,
                )

                save_appointment_details(
                    cur=cur,
                    appointment_id=appointment_id,
                    appointment_data=appointment_data,
                    patient_birth_date=patient_data["birth_date"],
                    patient_gender=patient_data["gender"],
                )

                conn.commit()

        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при сохранении пациента и приёма: {error}",
            )

    return AppointmentSaveResult(patient_id=patient_id, appointment_id=appointment_id)


def create_appointment_for_existing_patient(patient_id: int, form: Any) -> AppointmentSaveResult:
    """
    Создаёт новый приём для уже существующего пациента.

    Пациент заново не создаётся: используется patient_id из URL.
    Используется POST /api/patients/{patient_id}/appointments/new.
    """
    appointment_required = parse_required_appointment_fields(form)
    appointment_datetime = appointment_required["appointment_datetime"]

    validation_errors = validate_appointment_form(form, appointment_datetime.date())
    _raise_validation_errors(validation_errors)

    appointment_data = parse_appointment_form(form, appointment_datetime)

    with get_db_connection() as conn:
        try:
            with conn.cursor() as cur:
                patient = get_patient_for_appointment(cur, patient_id)

                if not patient:
                    raise HTTPException(status_code=404, detail="Пациент не найден")

                appointment_id = create_appointment(
                    cur=cur,
                    patient_id=patient_id,
                    doctor_id=appointment_required["doctor_id"],
                    location_id=appointment_required["location_id"],
                    appointment_datetime=appointment_datetime,
                )

                save_appointment_details(
                    cur=cur,
                    appointment_id=appointment_id,
                    appointment_data=appointment_data,
                    patient_birth_date=patient["birth_date"],
                    patient_gender=patient["gender"],
                )

                conn.commit()

        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при сохранении нового приёма: {error}",
            )

    return AppointmentSaveResult(patient_id=patient_id, appointment_id=appointment_id)
