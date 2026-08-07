"""Локальное предпочтение места приёма для конкретного браузера/компьютера.

Само право врача работать в месте приёма остаётся в doctor_locations.
Cookie лишь запоминает удобный выбор на данном компьютере и никогда не
подменяет серверную проверку doctor_locations при сохранении приёма.
"""
from __future__ import annotations

from typing import Any, Iterable

from fastapi import Request
from starlette.responses import Response

from app.repositories.reference_data import get_doctor_locations


ACTIVE_LOCATION_COOKIE_NAME = "mis_active_location"
ACTIVE_LOCATION_SESSION_KEY = "active_location_id"
ACTIVE_LOCATION_COOKIE_MAX_AGE = 365 * 24 * 60 * 60


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _allowed_ids(locations: Iterable[Any]) -> set[int]:
    result: set[int] = set()
    for location in locations or []:
        value = location.get("id") if hasattr(location, "get") else None
        parsed = _positive_int(value)
        if parsed is not None:
            result.add(parsed)
    return result


def get_cookie_active_location(
    request: Request,
    doctor_id: int,
    locations: Iterable[Any],
) -> int | None:
    """Читает preference-cookie только если она принадлежит этому врачу и месту."""
    raw = str(request.cookies.get(ACTIVE_LOCATION_COOKIE_NAME) or "").strip()
    if not raw or ":" not in raw:
        return None
    raw_doctor_id, raw_location_id = raw.split(":", 1)
    cookie_doctor_id = _positive_int(raw_doctor_id)
    cookie_location_id = _positive_int(raw_location_id)
    if cookie_doctor_id != int(doctor_id) or cookie_location_id is None:
        return None
    if cookie_location_id not in _allowed_ids(locations):
        return None
    return cookie_location_id


def choose_active_location_on_login(
    request: Request,
    doctor_id: int,
    locations: list[Any],
) -> int | None:
    """Восстанавливает выбор компьютера; единственное место выбирает автоматически."""
    cookie_location_id = get_cookie_active_location(request, doctor_id, locations)
    if cookie_location_id is not None:
        return cookie_location_id
    allowed = sorted(_allowed_ids(locations))
    if len(allowed) == 1:
        return allowed[0]
    return None


def get_session_active_location(request: Request, locations: Iterable[Any]) -> int | None:
    """Возвращает активное место из текущей сессии, если оно всё ещё разрешено."""
    location_id = _positive_int(request.session.get(ACTIVE_LOCATION_SESSION_KEY))
    if location_id is None:
        return None
    return location_id if location_id in _allowed_ids(locations) else None


def set_active_location_preference(
    request: Request,
    response: Response,
    doctor_id: int,
    location_id: int,
) -> None:
    """Сохраняет выбор в сессии и persistent cookie данного браузера."""
    doctor_id = int(doctor_id)
    location_id = int(location_id)
    request.session[ACTIVE_LOCATION_SESSION_KEY] = location_id
    response.set_cookie(
        key=ACTIVE_LOCATION_COOKIE_NAME,
        value=f"{doctor_id}:{location_id}",
        max_age=ACTIVE_LOCATION_COOKIE_MAX_AGE,
        path="/",
        httponly=True,
        samesite="lax",
    )


def remember_location_if_allowed(
    request: Request,
    response: Response,
    doctor_id: int,
    location_id_value: Any,
) -> bool:
    """Запоминает выбранное в форме место только если оно привязано к врачу."""
    location_id = _positive_int(location_id_value)
    if location_id is None:
        return False
    try:
        locations = get_doctor_locations(int(doctor_id))
    except Exception:
        # Предпочтение не должно превращать уже успешно сохранённый приём в 500.
        return False
    if location_id not in _allowed_ids(locations):
        return False
    set_active_location_preference(request, response, int(doctor_id), location_id)
    return True
