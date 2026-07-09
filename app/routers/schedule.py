"""
HTML-роуты минимального модуля расписания.

Первый этап:
- только роль admin;
- календарная таблица день / неделя / месяц / произвольный период;
- фильтр по врачу и отделению;
- создание слотов;
- запись пациента на свободный слот;
- отмена записи;
- ручная отметка "пришёл" / "не пришёл".

Медицинский приём в appointments здесь пока не создаётся.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.repositories.schedule import (
    SLOT_KIND_LABELS,
    book_schedule_slot,
    cancel_schedule_booking,
    generate_schedule_slots,
    get_schedule_doctors,
    get_schedule_locations_for_doctor,
    get_schedule_slots,
    set_schedule_booking_status,
)
from app.security.permissions import require_admin

router = APIRouter(tags=["schedule"])
templates = Jinja2Templates(directory="app/templates")

WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
ALLOWED_VIEW_MODES = {"day", "week", "month", "custom"}


def _parse_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


def _parse_required_date(value: str | None, field_name: str) -> date:
    if not value:
        raise HTTPException(status_code=400, detail=f"Не заполнено поле {field_name}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Некорректная дата: {field_name}") from exc


def _parse_time(value: str | None, field_name: str) -> time:
    if not value:
        raise HTTPException(status_code=400, detail=f"Не заполнено поле {field_name}")
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Некорректное время: {field_name}") from exc


def _parse_int(value: str | None, field_name: str, *, required: bool = True) -> int | None:
    if value in (None, ""):
        if required:
            raise HTTPException(status_code=400, detail=f"Не заполнено поле {field_name}")
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Некорректное значение: {field_name}") from exc


def _period_for_view(
    *,
    view_mode: str,
    anchor_date: date,
    date_from_value: str | None,
    date_to_value: str | None,
) -> tuple[date, date]:
    if view_mode == "day":
        return anchor_date, anchor_date

    if view_mode == "week":
        start = anchor_date - timedelta(days=anchor_date.weekday())
        return start, start + timedelta(days=6)

    if view_mode == "month":
        start = anchor_date.replace(day=1)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1)
        else:
            next_month = start.replace(month=start.month + 1)
        return start, next_month - timedelta(days=1)

    start = _parse_date(date_from_value, anchor_date)
    end = _parse_date(date_to_value, start)
    if end < start:
        end = start
    if (end - start).days > 31:
        end = start + timedelta(days=31)
    return start, end


def _shifted_anchor(view_mode: str, anchor_date: date, direction: int) -> date:
    if view_mode == "day":
        return anchor_date + timedelta(days=direction)
    if view_mode == "week":
        return anchor_date + timedelta(days=7 * direction)
    if view_mode == "month":
        year = anchor_date.year
        month = anchor_date.month + direction
        if month < 1:
            year -= 1
            month = 12
        elif month > 12:
            year += 1
            month = 1
        return anchor_date.replace(year=year, month=month, day=1)
    return anchor_date + timedelta(days=7 * direction)


def _build_schedule_url(
    *,
    view_mode: str,
    anchor_date: date,
    doctor_id: int | None,
    location_id: int | None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> str:
    params: dict[str, str | int] = {
        "view": view_mode,
        "date": anchor_date.isoformat(),
    }
    if doctor_id:
        params["doctor_id"] = doctor_id
    if location_id:
        params["location_id"] = location_id
    if view_mode == "custom" and date_from and date_to:
        params["date_from"] = date_from.isoformat()
        params["date_to"] = date_to.isoformat()
    return "/schedule?" + urlencode(params)


def _make_dates(date_from: date, date_to: date) -> list[dict]:
    today = date.today()
    result = []
    current = date_from
    while current <= date_to:
        result.append(
            {
                "value": current.isoformat(),
                "label": current.strftime("%d.%m"),
                "weekday": WEEKDAY_LABELS[current.weekday()],
                "is_today": current == today,
                "is_past": current < today,
            }
        )
        current += timedelta(days=1)
    return result


def _build_grid(slots: list[dict], dates: list[dict]) -> list[dict]:
    by_key = {(slot["date_iso"], slot["time_label"]): slot for slot in slots}
    time_labels = sorted({slot["time_label"] for slot in slots})

    rows = []
    for time_label in time_labels:
        rows.append(
            {
                "time_label": time_label,
                "cells": [by_key.get((day["value"], time_label)) for day in dates],
            }
        )
    return rows


def _period_label(date_from: date, date_to: date) -> str:
    if date_from == date_to:
        return date_from.strftime("%d.%m.%Y")
    return f"{date_from:%d.%m.%Y} — {date_to:%d.%m.%Y}"


def _redirect_back(request: Request) -> RedirectResponse:
    return RedirectResponse(request.headers.get("referer") or "/schedule", status_code=303)


@router.get("/schedule", response_class=HTMLResponse)
def schedule_page(
    request: Request,
    view: str = "week",
    date_value: str | None = Query(None, alias="date"),
    date_from: str | None = None,
    date_to: str | None = None,
    doctor_id: int | None = None,
    location_id: int | None = None,
):
    """Страница расписания администратора."""
    require_admin(request)

    view_mode = view if view in ALLOWED_VIEW_MODES else "week"
    anchor_date = _parse_date(date_value, default=date.today())
    start, end = _period_for_view(
        view_mode=view_mode,
        anchor_date=anchor_date,
        date_from_value=date_from,
        date_to_value=date_to,
    )

    doctors = get_schedule_doctors()
    if not doctors:
        return templates.TemplateResponse(
            "schedule/index.html",
            {
                "request": request,
                "doctors": [],
                "locations": [],
                "selected_doctor_id": None,
                "selected_location_id": None,
                "view_mode": view_mode,
                "anchor_date": anchor_date,
                "date_from": start,
                "date_to": end,
                "period_label": _period_label(start, end),
                "dates": [],
                "time_rows": [],
                "slot_kind_labels": SLOT_KIND_LABELS,
                "prev_url": "/schedule",
                "next_url": "/schedule",
                "message": "В справочнике нет врачей",
            },
        )

    if not doctor_id:
        doctor_id = int(doctors[0]["id"])

    locations = get_schedule_locations_for_doctor(doctor_id)
    selected_location_id = location_id

    slots = get_schedule_slots(
        doctor_id=doctor_id,
        location_id=selected_location_id,
        date_from=start,
        date_to=end,
    )
    dates = _make_dates(start, end)
    time_rows = _build_grid(slots, dates)

    prev_anchor = _shifted_anchor(view_mode, anchor_date, -1)
    next_anchor = _shifted_anchor(view_mode, anchor_date, 1)

    context = {
        "request": request,
        "doctors": doctors,
        "locations": locations,
        "selected_doctor_id": doctor_id,
        "selected_location_id": selected_location_id,
        "view_mode": view_mode,
        "anchor_date": anchor_date,
        "date_from": start,
        "date_to": end,
        "period_label": _period_label(start, end),
        "dates": dates,
        "time_rows": time_rows,
        "slot_kind_labels": SLOT_KIND_LABELS,
        "prev_url": _build_schedule_url(
            view_mode=view_mode,
            anchor_date=prev_anchor,
            doctor_id=doctor_id,
            location_id=selected_location_id,
            date_from=start,
            date_to=end,
        ),
        "next_url": _build_schedule_url(
            view_mode=view_mode,
            anchor_date=next_anchor,
            doctor_id=doctor_id,
            location_id=selected_location_id,
            date_from=start,
            date_to=end,
        ),
        "message": None,
    }
    return templates.TemplateResponse("schedule/index.html", context)


@router.post("/schedule/slots/generate")
async def schedule_generate_slots(request: Request):
    """Создаёт сетку свободных слотов."""
    require_admin(request)
    form = await request.form()

    doctor_id = _parse_int(form.get("doctor_id"), "Врач")
    location_id = _parse_int(form.get("location_id"), "Отделение")
    start = _parse_required_date(form.get("date_from"), "Дата с")
    end = _parse_required_date(form.get("date_to"), "Дата по")
    time_from = _parse_time(form.get("time_from"), "Время с")
    time_to = _parse_time(form.get("time_to"), "Время по")
    slot_minutes = _parse_int(form.get("slot_minutes"), "Длительность слота") or 30
    slot_kind = str(form.get("slot_kind") or "primary")
    weekdays = {int(value) for value in form.getlist("weekdays") if str(value).isdigit()}
    note = str(form.get("note") or "").strip() or None

    generate_schedule_slots(
        doctor_id=int(doctor_id),
        location_id=int(location_id),
        date_from=start,
        date_to=end,
        weekdays=weekdays,
        time_from=time_from,
        time_to=time_to,
        slot_minutes=int(slot_minutes),
        slot_kind=slot_kind,
        note=note,
        created_by_user_id=request.session.get("user_id"),
    )

    return RedirectResponse(
        url=_build_schedule_url(
            view_mode="week",
            anchor_date=start,
            doctor_id=int(doctor_id),
            location_id=int(location_id),
        ),
        status_code=303,
    )


@router.post("/schedule/slots/{slot_id}/book")
async def schedule_book_slot(slot_id: int, request: Request):
    """Записывает пациента на свободный слот."""
    require_admin(request)
    form = await request.form()

    birth_date = _parse_required_date(form.get("birth_date"), "Дата рождения")
    gender_raw = str(form.get("gender") or "true")
    gender = gender_raw == "true"

    book_schedule_slot(
        slot_id=slot_id,
        last_name=str(form.get("last_name") or ""),
        first_name=str(form.get("first_name") or ""),
        patronymic=str(form.get("patronymic") or "").strip() or None,
        birth_date=birth_date,
        gender=gender,
        reason=str(form.get("reason") or "").strip() or None,
        comment=str(form.get("comment") or "").strip() or None,
        booked_by_user_id=request.session.get("user_id"),
    )
    return _redirect_back(request)


@router.post("/schedule/bookings/{booking_id}/cancel")
async def schedule_cancel_booking(booking_id: int, request: Request):
    """Отменяет запись пациента на слот."""
    require_admin(request)
    form = await request.form()
    cancel_schedule_booking(
        booking_id=booking_id,
        cancelled_by_user_id=request.session.get("user_id"),
        cancel_reason=str(form.get("cancel_reason") or "").strip() or None,
    )
    return _redirect_back(request)


@router.post("/schedule/bookings/{booking_id}/status")
async def schedule_change_booking_status(booking_id: int, request: Request):
    """Отмечает прошедшую запись: пациент пришёл или не пришёл."""
    require_admin(request)
    form = await request.form()
    set_schedule_booking_status(
        booking_id=booking_id,
        status=str(form.get("status") or ""),
    )
    return _redirect_back(request)
