"""
Что тестируется:
- новые тонкие роутеры после дробления patients.py;
- POST нового пациента вызывает create_patient_with_first_appointment;
- POST нового приёма вызывает create_appointment_for_existing_patient;
- фильтры приёмов вызывают get_all_appointments с ожидаемым словарём фильтров;
- даты в JSON-ответе фильтров сериализуются в isoformat.

Зачем:
patients.py был разделён на несколько роутеров. Эти тесты проверяют, что URL-слой
не потерял связь с сервисами и базовыми API фильтрации.

Тесты НЕ запускают сервер и НЕ пишут в БД.

Важно:
роуты создания пациента и приёма являются async-функциями FastAPI.
Чтобы не добавлять отдельную dev-зависимость pytest-asyncio, мы запускаем их
через anyio.run(...). AnyIO уже используется FastAPI/Starlette, поэтому такая
проверка не требует дополнительных пакетов.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import anyio

import app.routers.appointment_filters as filters_router
import app.routers.appointments as appointments_router
import app.routers.patients as patients_router

from .factories import full_fake_form


@dataclass
class FakeSaveResult:
    patient_id: int
    appointment_id: int


class FakeRequest:
    async def form(self):
        return full_fake_form()


def test_create_new_patient_router_redirects_to_patient_card(monkeypatch):
    """
    Проверяет POST-роут создания нового пациента.

    Что важно:
    - роут получает form из request;
    - передаёт форму в сервис create_patient_with_first_appointment;
    - получает patient_id и appointment_id;
    - возвращает redirect на карточку пациента.

    БД не используется: сервис подменяется monkeypatch.
    """
    called = {}

    def fake_create_patient_with_first_appointment(form):
        called["form"] = form
        return FakeSaveResult(patient_id=101, appointment_id=202)

    monkeypatch.setattr(
        patients_router,
        "create_patient_with_first_appointment",
        fake_create_patient_with_first_appointment,
    )

    response = anyio.run(patients_router.create_new_patient, FakeRequest())

    assert response.status_code == 303
    assert response.headers["location"] == "/patient/101?appointment_id=202"
    assert called["form"].get("last_name") == "Тестова"


def test_create_new_appointment_router_redirects_to_patient_card(monkeypatch):
    """
    Проверяет POST-роут создания повторного приёма старому пациенту.

    Что важно:
    - роут получает patient_id из URL;
    - получает form из request;
    - передаёт patient_id и form в create_appointment_for_existing_patient;
    - возвращает redirect на карточку пациента с новым appointment_id.

    БД не используется: сервис подменяется monkeypatch.
    """
    called = {}

    def fake_create_appointment_for_existing_patient(patient_id, form):
        called["patient_id"] = patient_id
        called["form"] = form
        return FakeSaveResult(patient_id=101, appointment_id=303)

    monkeypatch.setattr(
        appointments_router,
        "create_appointment_for_existing_patient",
        fake_create_appointment_for_existing_patient,
    )

    response = anyio.run(
        appointments_router.create_new_appointment_for_existing_patient,
        101,
        FakeRequest(),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/patient/101?appointment_id=303"
    assert called["patient_id"] == 101
    assert called["form"].get("last_name") == "Тестова"


def test_api_appointments_filtered_builds_filters_and_serializes_dates(monkeypatch):
    """
    Проверяет API фильтрации приёмов.

    Что важно:
    - branch_id, location_id, doctor_id, search, period, limit, offset
      собираются в словарь фильтров;
    - роут вызывает get_all_appointments;
    - даты datetime/date переводятся в строки, пригодные для JSON.

    БД не используется: get_all_appointments подменяется monkeypatch.
    """
    captured = {}

    def fake_get_all_appointments(filters):
        captured["filters"] = filters
        return [
            {
                "id": 202,
                "patient_id": 101,
                "appointment_date": datetime(2026, 7, 4, 10, 30),
                "birth_date": date(1980, 1, 15),
            }
        ]

    monkeypatch.setattr(filters_router, "get_all_appointments", fake_get_all_appointments)

    result = filters_router.api_appointments_filtered(
        branch_id=1,
        location_id=2,
        doctor_id=3,
        search="Тестова",
        period="today",
        limit=10,
        offset=0,
    )

    assert captured["filters"]["branch_id"] == 1
    assert captured["filters"]["location_id"] == 2
    assert captured["filters"]["doctor_id"] == 3
    assert captured["filters"]["search"] == "Тестова"

    # period="today" внутри роутера не передаётся в БД как отдельный ключ.
    # Он преобразуется в date_from/date_to, потому что слой БД фильтрует
    # приёмы уже по конкретному диапазону дат.
    assert captured["filters"]["date_from"] == date.today()
    assert captured["filters"]["date_to"] == date.today()

    assert captured["filters"]["sort_order"] == "desc"
    assert captured["filters"]["limit"] == 10
    assert captured["filters"]["offset"] == 0

    assert result[0]["appointment_date"].startswith("2026-07-04")
    assert result[0]["birth_date"] == "1980-01-15"


def test_filter_dictionaries_delegate_to_database_functions(monkeypatch):
    """
    Проверяет API справочников для фильтров главной страницы.

    Что важно:
    - /api/branches вызывает get_branches;
    - /api/locations вызывает get_locations_for_filter;
    - /api/doctors вызывает get_doctors_for_filter;
    - /api/doctor-locations/{doctor_id} вызывает get_doctor_locations.

    БД не используется: все функции получения справочников подменяются monkeypatch.
    """
    monkeypatch.setattr(filters_router, "get_branches", lambda: [{"id": 1, "name": "Филиал"}])
    monkeypatch.setattr(
        filters_router,
        "get_locations_for_filter",
        lambda branch_id=None, doctor_id=None: [{"id": 2, "name": "Отделение"}],
    )
    monkeypatch.setattr(
        filters_router,
        "get_doctors_for_filter",
        lambda branch_id=None, location_id=None: [{"id": 3, "name": "Врач"}],
    )
    monkeypatch.setattr(
        filters_router,
        "get_doctor_locations",
        lambda doctor_id: [{"id": 2, "name": "Отделение"}],
    )

    assert filters_router.api_branches()[0]["id"] == 1
    assert filters_router.api_locations(branch_id=1)[0]["id"] == 2
    assert filters_router.api_doctors(branch_id=1)[0]["id"] == 3
    assert filters_router.api_doctor_locations(doctor_id=3)[0]["id"] == 2