"""
API фильтров главной страницы со списком приёмов.

Этот роутер вынесен из patients.py, потому что фильтры приёмов — это отдельная задача интерфейса, а не создание пациента или сохранение приёма.

Здесь остаются только GET API:
- список отфильтрованных приёмов;
- филиалы;
- отделения;
- врачи;
- отделения конкретного врача.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter

from ..database import (
    get_all_appointments,
    get_branches,
    get_doctor_locations,
    get_doctors_for_filter,
    get_locations_for_filter,
)

router = APIRouter(tags=["appointment_filters"])


@router.get("/api/appointments/filtered")
def api_appointments_filtered(
    branch_id: Optional[int] = None,
    location_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    search: Optional[str] = None,
    period: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    sort_order: str = "desc",
    limit: int = 200,
    offset: int = 0,
):
    """Возвращает отфильтрованный список приёмов в формате JSON."""
    today = date.today()

    if period == "today" and not date_from and not date_to:
        date_from = today
        date_to = today
    elif period == "week" and not date_from and not date_to:
        date_from = today - timedelta(days=7)
        date_to = today
    elif period == "month" and not date_from and not date_to:
        date_from = today - timedelta(days=30)
        date_to = today
    elif period == "year" and not date_from and not date_to:
        date_from = date(today.year - 1, today.month, today.day)
        date_to = today
    elif period == "oldest":
        sort_order = "asc"
    elif period == "newest":
        sort_order = "desc"

    filters = {
        "branch_id": branch_id,
        "location_id": location_id,
        "doctor_id": doctor_id,
        "search": search,
        "date_from": date_from,
        "date_to": date_to,
        "sort_order": sort_order,
        "limit": limit,
        "offset": offset,
    }

    appointments = get_all_appointments(filters)
    result = []

    for appointment in appointments:
        appointment_dict = dict(appointment)

        if appointment_dict.get("appointment_date"):
            appointment_dict["appointment_date"] = appointment_dict["appointment_date"].isoformat()

        if appointment_dict.get("birth_date"):
            appointment_dict["birth_date"] = appointment_dict["birth_date"].isoformat()

        result.append(appointment_dict)

    return result


@router.get("/api/branches")
def api_branches():
    """Возвращает список филиалов."""
    return get_branches()


@router.get("/api/locations")
def api_locations(
    branch_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
):
    """
    Возвращает список отделений для фильтра.

    Может учитывать выбранный филиал и/или выбранного врача.
    """
    if not branch_id and not doctor_id:
        return []

    return get_locations_for_filter(branch_id=branch_id, doctor_id=doctor_id)


@router.get("/api/doctors")
def api_doctors(
    branch_id: Optional[int] = None,
    location_id: Optional[int] = None,
):
    """
    Возвращает список врачей для фильтра.

    Может учитывать выбранный филиал и/или выбранное отделение.
    """
    return get_doctors_for_filter(branch_id=branch_id, location_id=location_id)


@router.get("/api/doctor-locations/{doctor_id}")
def api_doctor_locations(doctor_id: int):
    """Возвращает отделения, где работает врач."""
    return get_doctor_locations(doctor_id)
