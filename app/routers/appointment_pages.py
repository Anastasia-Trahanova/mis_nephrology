"""HTML-страницы форм приёма."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.repositories.schedule import (
    get_schedule_entry_for_appointment_form,
    get_schedule_location_by_id,
)
from app.security.permissions import require_doctor_with_id
from app.services.appointment_form_context_service import (
    get_new_appointment_context,
    get_new_patient_context,
)

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


def _add_scheduled_location(context: dict, schedule_entry: dict) -> None:
    scheduled_location = get_schedule_location_by_id(int(schedule_entry["location_id"]))
    locations = list(context.get("doctor_locations") or [])
    existing_ids = {int(item["id"]) for item in locations}
    if scheduled_location and int(scheduled_location["id"]) not in existing_ids:
        locations.append(scheduled_location)
    context["doctor_locations"] = locations
    context["locations"] = locations


@router.get("/new-patient", response_class=HTMLResponse)
def new_patient_form(request: Request, schedule_entry_id: int | None = None):
    """Форма создания пациента либо первичного приёма из расписания."""
    current_doctor_id = require_doctor_with_id(request)
    now = datetime.now()

    if schedule_entry_id is None:
        context = get_new_patient_context(current_doctor_id)
        context.update(
            {
                "request": request,
                "now_date": now.strftime("%Y-%m-%d"),
                "now_time": now.strftime("%H:%M"),
                "schedule_existing_patient": False,
                "schedule_entry": None,
            }
        )
        return templates.TemplateResponse(request=request, name="new_patient.html", context=context)

    schedule_entry = get_schedule_entry_for_appointment_form(schedule_entry_id)
    if schedule_entry.get("appointment_type") != "primary":
        return RedirectResponse(
            url=(
                f"/new-appointment/{schedule_entry['patient_id']}"
                f"?schedule_entry_id={schedule_entry_id}"
            ),
            status_code=303,
        )

    context = get_new_appointment_context(
        int(schedule_entry["patient_id"]),
        current_doctor_id,
    )
    if not context:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    _add_scheduled_location(context, schedule_entry)
    context.update(
        {
            "request": request,
            "now_date": schedule_entry["date_iso"],
            "now_time": schedule_entry["start_time"],
            "schedule_existing_patient": True,
            "schedule_entry": schedule_entry,
        }
    )
    return templates.TemplateResponse(request=request, name="new_patient.html", context=context)


@router.get("/new-appointment/{patient_id}", response_class=HTMLResponse)
def new_appointment_form(
    request: Request,
    patient_id: int,
    schedule_entry_id: int | None = None,
):
    """Форма повторного приёма."""
    current_doctor_id = require_doctor_with_id(request)
    context = get_new_appointment_context(patient_id, current_doctor_id)
    if not context:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    schedule_entry = None
    if schedule_entry_id is not None:
        schedule_entry = get_schedule_entry_for_appointment_form(schedule_entry_id, patient_id)
        if schedule_entry.get("appointment_type") == "primary":
            return RedirectResponse(
                url=f"/new-patient?schedule_entry_id={schedule_entry_id}",
                status_code=303,
            )
        _add_scheduled_location(context, schedule_entry)

    now = datetime.now()
    context.update(
        {
            "request": request,
            "now_date": schedule_entry["date_iso"] if schedule_entry else now.strftime("%Y-%m-%d"),
            "now_time": schedule_entry["start_time"] if schedule_entry else now.strftime("%H:%M"),
            "schedule_entry": schedule_entry,
        }
    )
    return templates.TemplateResponse(request=request, name="new_appointment.html", context=context)
