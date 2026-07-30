"""Страница и JSON API расписания."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.repositories.schedule import (
    create_schedule_entry,
    create_walk_in_schedule_entry,
    get_schedule_doctors,
    get_schedule_entries,
    get_schedule_entry,
    get_schedule_locations_for_doctor,
    get_patient_upcoming_schedule_entry,
    search_schedule_patients,
    set_schedule_entry_status,
    update_schedule_entry,
)
from app.security.permissions import (
    ROLE_ADMIN,
    ROLE_DOCTOR,
    require_doctor_with_id,
    require_roles,
)

router = APIRouter(tags=["schedule"])
templates = Jinja2Templates(directory="app/templates")

WEEKDAYS = (
    "Понедельник", "Вторник", "Среда", "Четверг",
    "Пятница", "Суббота", "Воскресенье",
)
MONTHS_GENITIVE = (
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


class ScheduleEntryPayload(BaseModel):
    appointment_date: date
    scheduled_doctor_id: int
    location_id: int
    starts_at: time
    ends_at: time
    patient_id: int | None = None
    last_name: str | None = None
    first_name: str | None = None
    patronymic: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    gender: bool | None = None


class ScheduleEntryEditPayload(ScheduleEntryPayload):
    patient_mode: str = "selected"


class ScheduleStatusPayload(BaseModel):
    status: str
    cancel_reason: str | None = None


class WalkInAppointmentPayload(BaseModel):
    action: str
    scheduled_entry_id: int | None = None


def _require_schedule_access(request: Request) -> None:
    require_roles(request, ROLE_ADMIN, ROLE_DOCTOR)


def _parse_iso_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


def _monday(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _date_label(value: date) -> str:
    return f"{value.day} {MONTHS_GENITIVE[value.month]} {value.year}"


def _week_label(start: date) -> str:
    return f"{start:%d.%m.%Y} — {start + timedelta(days=6):%d.%m.%Y}"


def _week_days(start: date) -> list[dict]:
    today = date.today()
    return [
        {
            "iso": (day := start + timedelta(days=index)).isoformat(),
            "weekday": WEEKDAYS[index],
            "short_date": day.strftime("%d.%m"),
            "date_label": _date_label(day),
            "is_today": day == today,
            "is_weekend": index >= 5,
        }
        for index in range(7)
    ]


def _week_options(selected_start: date) -> list[dict]:
    return [
        {
            "value": (start := selected_start + timedelta(days=7 * offset)).isoformat(),
            "label": _week_label(start),
            "selected": offset == 0,
        }
        for offset in range(-8, 9)
    ]


def _validated_doctor_id(value: int | None, doctors: list[dict]) -> int | None:
    return value if value and any(int(item["id"]) == value for item in doctors) else None


def _combine(day: date, value: time) -> datetime:
    return datetime.combine(day, value.replace(second=0, microsecond=0))


@router.get("/schedule", response_class=HTMLResponse)
def schedule_page(request: Request, doctor_id: int | None = None, week: str | None = Query(None)):
    _require_schedule_access(request)
    selected_week = _monday(_parse_iso_date(week, date.today()))
    doctors = get_schedule_doctors()

    requested_doctor_id = doctor_id
    if requested_doctor_id is None and request.session.get("role") == ROLE_DOCTOR:
        try:
            requested_doctor_id = int(request.session.get("doctor_id"))
        except (TypeError, ValueError):
            requested_doctor_id = None

    selected_doctor_id = _validated_doctor_id(requested_doctor_id, doctors)
    locations = get_schedule_locations_for_doctor(selected_doctor_id) if selected_doctor_id else []

    return templates.TemplateResponse(
        request=request,
        name="schedule/index.html",
        context={
            "request": request,
            "doctors": doctors,
            "locations": locations,
            "selected_doctor_id": selected_doctor_id,
            "selected_week": selected_week.isoformat(),
            "week_label": _week_label(selected_week),
            "week_days": _week_days(selected_week),
            "week_options": _week_options(selected_week),
            "can_start_appointment": request.session.get("role") == ROLE_DOCTOR
            and bool(request.session.get("doctor_id")),
        },
    )


@router.get("/schedule/api/doctors/{doctor_id}/locations")
def schedule_doctor_locations(doctor_id: int, request: Request):
    _require_schedule_access(request)
    if doctor_id <= 0:
        raise HTTPException(status_code=400, detail="Некорректный врач")
    return {"items": get_schedule_locations_for_doctor(doctor_id)}


@router.get("/schedule/api/entries")
def schedule_entries_api(
    request: Request,
    doctor_id: int,
    date_from: date,
    date_to: date,
):
    _require_schedule_access(request)
    if date_to < date_from or (date_to - date_from).days > 62:
        raise HTTPException(status_code=400, detail="Некорректный период")
    return {"items": get_schedule_entries(doctor_id=doctor_id, date_from=date_from, date_to=date_to)}


@router.get("/schedule/api/patients/search")
def schedule_patient_search(
    request: Request,
    last_name: str = "",
    first_name: str = "",
    patronymic: str = "",
):
    _require_schedule_access(request)
    return {
        "items": search_schedule_patients(
            last_name=last_name,
            first_name=first_name,
            patronymic=patronymic,
        )
    }


@router.post("/schedule/api/entries", status_code=201)
def schedule_create_entry(payload: ScheduleEntryPayload, request: Request):
    _require_schedule_access(request)
    item = create_schedule_entry(
        scheduled_doctor_id=payload.scheduled_doctor_id,
        location_id=payload.location_id,
        starts_at=_combine(payload.appointment_date, payload.starts_at),
        ends_at=_combine(payload.appointment_date, payload.ends_at),
        patient_id=payload.patient_id,
        last_name=payload.last_name,
        first_name=payload.first_name,
        patronymic=payload.patronymic,
        birth_date=payload.birth_date,
        phone=payload.phone,
        gender=payload.gender,
        created_by_user_id=request.session.get("user_id"),
    )
    return {"item": item}


@router.get("/schedule/api/entries/{entry_id}")
def schedule_entry_details(entry_id: int, request: Request):
    """Возвращает данные записи для выбора действия по ФИО пациента."""
    _require_schedule_access(request)
    item = get_schedule_entry(entry_id)
    return {
        "item": {
            "id": item["id"],
            "patient_id": item["patient_id"],
            "patient_fio": item.get("patient_fio"),
            "date_iso": item["date_iso"],
            "starts_at": item["starts_at"],
            "appointment_id": item.get("appointment_id"),
        }
    }


@router.put("/schedule/api/entries/{entry_id}")
def schedule_update_entry(entry_id: int, payload: ScheduleEntryEditPayload, request: Request):
    _require_schedule_access(request)
    item = update_schedule_entry(
        entry_id=entry_id,
        scheduled_doctor_id=payload.scheduled_doctor_id,
        location_id=payload.location_id,
        starts_at=_combine(payload.appointment_date, payload.starts_at),
        ends_at=_combine(payload.appointment_date, payload.ends_at),
        patient_id=payload.patient_id,
        patient_mode=payload.patient_mode,
        last_name=payload.last_name,
        first_name=payload.first_name,
        patronymic=payload.patronymic,
        birth_date=payload.birth_date,
        phone=payload.phone,
        gender=payload.gender,
    )
    return {"item": item}


@router.patch("/schedule/api/entries/{entry_id}/status")
def schedule_update_status(entry_id: int, payload: ScheduleStatusPayload, request: Request):
    _require_schedule_access(request)
    item = set_schedule_entry_status(
        entry_id=entry_id,
        status=payload.status,
        user_id=request.session.get("user_id"),
        cancel_reason=payload.cancel_reason,
    )
    return {"item": item}

def _walk_in_date_time_label(item: dict) -> str:
    starts_at = datetime.fromisoformat(str(item["starts_at"]))
    return f"{starts_at.day} {MONTHS_GENITIVE[starts_at.month]} в {starts_at:%H:%M}"


@router.get("/schedule/api/patients/{patient_id}/upcoming-entry")
def patient_upcoming_schedule_entry(patient_id: int, request: Request):
    require_doctor_with_id(request)
    item = get_patient_upcoming_schedule_entry(
        patient_id=patient_id,
        now=datetime.now(),
        days=30,
    )
    if not item:
        return {"item": None, "period_days": 30}
    return {
        "item": {
            "id": item["id"],
            "label": _walk_in_date_time_label(item),
            "starts_at": item["starts_at"],
            "doctor_fio": item.get("scheduled_doctor_fio"),
        },
        "period_days": 30,
    }


@router.post("/schedule/api/patients/{patient_id}/walk-in", status_code=201)
def patient_create_walk_in(
    patient_id: int,
    payload: WalkInAppointmentPayload,
    request: Request,
):
    doctor_id = require_doctor_with_id(request)
    allowed_actions = {"create", "keep_and_create", "cancel_and_create"}
    if payload.action not in allowed_actions:
        raise HTTPException(status_code=400, detail="Некорректное действие")
    if payload.action == "cancel_and_create" and not payload.scheduled_entry_id:
        raise HTTPException(status_code=400, detail="Не указана отменяемая запись")

    item = create_walk_in_schedule_entry(
        patient_id=patient_id,
        doctor_id=doctor_id,
        created_by_user_id=request.session.get("user_id"),
        cancel_entry_id=(
            payload.scheduled_entry_id
            if payload.action == "cancel_and_create"
            else None
        ),
        now=datetime.now(),
    )
    return {
        "item": item,
        "redirect_url": (
            f"/new-appointment/{patient_id}?schedule_entry_id={item['id']}"
        ),
    }

