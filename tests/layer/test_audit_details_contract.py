"""
Назначение файла: contract-тесты подробного аудита медицинских изменений.

Как работает:
- не подключается к реальной БД;
- проверяет, что app/services/audit_details.py правильно классифицирует изменения формы;
- проверяет, что для сохранённого приёма появляются подробности по анализам, МКБ-10,
  KDIGO, рекомендациям и лекарствам;
- проверяет, что admin может открыть страницу подробностей события, а doctor получает 403.

Что редактировать здесь:
- ожидаемые статусы изменений, если меняется модель audit_event_changes;
- тестовые имена полей формы при изменении HTML-шаблонов.

Что не редактировать здесь:
- реальные пароли;
- реальные SQL-запросы;
- медицинские формулы расчёта СКФ, ACR и KDIGO.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from starlette.datastructures import FormData
from starlette.middleware.sessions import SessionMiddleware

from app.repositories import audit_log
from app.routers import admin as admin_router
from app.services.audit_details import (
    build_appointment_medical_audit_changes,
    build_patient_creation_audit_changes,
)


TEST_SESSION_COOKIE = "test_audit_details_session"


def change_types(changes):
    """Возвращает множество статусов изменений из списка audit_event_changes."""
    return {change["change_type"] for change in changes}


def find_change(changes, *, section=None, field_name=None, change_type=None):
    """Ищет одно изменение по разделу/полю/типу."""
    for change in changes:
        if section is not None and change.get("section") != section:
            continue
        if field_name is not None and change.get("field_name") != field_name:
            continue
        if change_type is not None and change.get("change_type") != change_type:
            continue
        return change
    return None


def test_01_patient_creation_builds_patient_and_appointment_changes():
    form = FormData(
        [
            ("last_name", "Волкова"),
            ("first_name", "Татьяна"),
            ("patronymic", "Николаевна"),
            ("birth_date", "1960-01-01"),
            ("gender", "false"),
            ("phone", "+7 900 000-00-00"),
            ("appointment_date", "2026-07-09"),
            ("appointment_time", "10:00"),
            ("doctor_id", "1"),
            ("location_id", "1"),
        ]
    )

    changes = build_patient_creation_audit_changes(
        form,
        patient_id=6,
        appointment_id=28,
    )

    assert find_change(changes, section="patient", change_type="patient_created")
    assert find_change(changes, section="appointment", change_type="appointment_created")
    assert find_change(changes, section="patient", field_name="last_name")
    assert find_change(changes, section="patient", field_name="phone")
    assert find_change(changes, section="appointment", field_name="appointment_date")


def test_02_prefilled_text_changed_is_logged():
    form = FormData([("complaints", "Слабость, отёки к вечеру")])
    previous = {"complaints": "Слабость"}

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment=previous,
        previous_medications=[],
        appointment_id=28,
    )

    change = find_change(changes, section="survey", field_name="complaints")
    assert change["change_type"] == "changed_from_prefill"
    assert change["old_value"] == "Слабость"
    assert change["new_value"] == "Слабость, отёки к вечеру"


def test_03_prefilled_text_cleared_is_logged():
    form = FormData([("heredity_description", "")])
    previous = {"heredity_description": "У матери сахарный диабет"}

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment=previous,
        previous_medications=[],
        appointment_id=28,
    )

    change = find_change(changes, section="survey", field_name="heredity_description")
    assert change["change_type"] == "cleared_from_prefill"
    assert "подставленное" in change["details"]


def test_04_new_text_filled_is_logged():
    form = FormData([("past_diseases", "Гипертоническая болезнь")])

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment={},
        previous_medications=[],
        appointment_id=28,
    )

    change = find_change(changes, section="survey", field_name="past_diseases")
    assert change["change_type"] == "filled_new"
    assert change["new_value"] == "Гипертоническая болезнь"


def test_05_unchanged_prefilled_text_is_not_logged():
    form = FormData([("habitual_intoxications", "Курит 30 лет")])
    previous = {"habitual_intoxications": "Курит 30 лет"}

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment=previous,
        previous_medications=[],
        appointment_id=28,
    )

    assert not find_change(
        changes, section="survey", field_name="habitual_intoxications"
    )


def test_06_biochemistry_added_and_gfr_autocalculated_are_logged():
    form = FormData(
        [
            ("biochemistry_investigation_date", "2026-07-09"),
            ("creatinine", "110"),
            ("urea", "8.2"),
        ]
    )

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment={},
        previous_medications=[],
        appointment_id=28,
    )

    lab = find_change(changes, section="biochemistry", change_type="lab_added")
    calc = find_change(changes, section="biochemistry", change_type="autocalculated")
    assert lab
    assert "Креатинин: 110" in lab["details"]
    assert calc
    assert "СКФ" in calc["details"]


def test_07_albuminuria_added_and_acr_autocalculated_are_logged():
    form = FormData(
        [
            ("albuminuria_investigation_date", "2026-07-09"),
            ("urine_albumin", "30"),
            ("urine_creatinine", "10"),
        ]
    )

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment={},
        previous_medications=[],
        appointment_id=28,
    )

    assert find_change(changes, section="albuminuria", change_type="lab_added")
    assert find_change(changes, section="albuminuria", change_type="autocalculated")


def test_08_empty_lab_row_is_not_logged():
    form = FormData(
        [
            ("biochemistry_investigation_date", "2026-07-09"),
            ("creatinine", ""),
            ("urea", ""),
        ]
    )

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment={},
        previous_medications=[],
        appointment_id=28,
    )

    assert not find_change(changes, section="biochemistry", change_type="lab_added")


def test_09_icd10_main_accepts_system_suggestion_when_form_provides_it():
    form = FormData(
        [
            ("icd10_main_diagnosis_suggested", "N18.2 — Хроническая болезнь почек, стадия 2"),
            ("icd10_main_diagnosis", "N18.2 — Хроническая болезнь почек, стадия 2"),
        ]
    )

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment={},
        previous_medications=[],
        appointment_id=28,
    )

    assert find_change(changes, section="icd10", change_type="system_suggested_main")
    assert find_change(changes, section="icd10", change_type="accepted_system_main")


def test_10_icd10_main_override_is_logged_when_doctor_replaces_system_value():
    form = FormData(
        [
            ("icd10_main_diagnosis_suggested", "N18.2 — Хроническая болезнь почек, стадия 2"),
            ("icd10_main_diagnosis", "N18.3 — Хроническая болезнь почек, стадия 3"),
        ]
    )

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment={},
        previous_medications=[],
        appointment_id=28,
    )

    change = find_change(changes, section="icd10", change_type="overridden_system_main")
    assert change
    assert change["old_value"].startswith("N18.2")
    assert change["new_value"].startswith("N18.3")


def test_11_icd10_complications_and_notes_are_logged():
    form = FormData(
        [
            ("icd10_complication_diagnosis", "I15.1 — Гипертензия вторичная"),
            ("icd10_complication_note", "почечный генез"),
        ]
    )

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment={},
        previous_medications=[],
        appointment_id=28,
    )

    change = find_change(changes, section="icd10", field_name="icd10_complication_diagnosis")
    assert change["change_type"] == "diagnosis_added"
    assert change["details"] == "почечный генез"


def test_12_kdigo_selected_option_is_logged():
    form = FormData(
        [
            ("kdigo_selected_current_option", "2026-07-09|С2|2026-07-09|A2"),
            (
                "kdigo_selected_conclusion_text",
                "По KDIGO: C2A2 — умеренно повышенный риск прогрессирования ХБП",
            ),
        ]
    )

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment={},
        previous_medications=[],
        appointment_id=28,
    )

    change = find_change(changes, section="kdigo", change_type="selected_by_doctor")
    assert change
    assert "C2A2" in change["new_value"]


def test_13_diet_recommendations_and_control_date_changes_are_logged():
    form = FormData(
        [
            ("diet", "Стол №7"),
            ("recommendations", "Контроль АД ежедневно"),
            ("next_control_date", "2026-09-01"),
        ]
    )
    previous = {
        "diet": "Стол №7 с ограничением соли",
        "recommendations": "Контроль АД" ,
        "next_control_date": None,
    }

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment=previous,
        previous_medications=[],
        appointment_id=28,
    )

    assert find_change(changes, section="diet", field_name="diet", change_type="changed_from_prefill")
    assert find_change(changes, section="diet", field_name="recommendations", change_type="changed_from_prefill")
    assert find_change(changes, section="diet", field_name="next_control_date", change_type="date_set")


def test_14_medication_added_continued_changed_and_removed_are_logged():
    form = FormData(
        [
            ("medication", "Эналаприл"),
            ("dosage", "10 мг"),
            ("schedule", "утром"),
            ("medication", "Фуросемид"),
            ("dosage", "20 мг"),
            ("schedule", "утром"),
            ("medication", "Амлодипин"),
            ("dosage", "5 мг"),
            ("schedule", "вечером"),
        ]
    )
    previous_medications = [
        {"medication": "Эналаприл", "dosage": "10 мг", "schedule": "утром"},
        {"medication": "Фуросемид", "dosage": "40 мг", "schedule": "утром"},
        {"medication": "Аспирин", "dosage": "100 мг", "schedule": "после еды"},
    ]

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment={},
        previous_medications=previous_medications,
        appointment_id=28,
    )
    types = change_types(changes)

    assert "medication_continued" in types
    assert "dosage_changed" in types
    assert "medication_added" in types
    assert "medication_removed" in types


def test_15_changes_are_grouped_by_section_for_detail_template():
    changes = [
        {"section": "survey", "section_label": "Опрос", "change_type": "filled_new"},
        {"section": "survey", "section_label": "Опрос", "change_type": "changed_from_prefill"},
        {"section": "medications", "section_label": "Лекарства", "change_type": "medication_added"},
    ]

    grouped = audit_log.group_audit_changes_by_section(changes)

    assert len(grouped) == 2
    assert grouped[0]["section"] == "survey"
    assert len(grouped[0]["changes"]) == 2
    assert grouped[1]["section"] == "medications"


def test_16_repository_decorates_change_type_labels():
    change = audit_log._decorate_change(  # noqa: SLF001 - contract test for internal decorator
        {"change_type": "medication_added", "section": "medications"}
    )

    assert change["change_type_label"] == "Добавлен препарат"


@pytest.fixture()
def admin_detail_app(monkeypatch):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret-key",
        session_cookie=TEST_SESSION_COOKIE,
        max_age=604800,
        same_site="lax",
        https_only=False,
    )

    @app.get("/set-admin")
    def set_admin(request: Request):
        request.session.update(
            {
                "user_id": 1,
                "login": "admin",
                "display_name": "Администратор",
                "role": "admin",
                "last_seen_at": 1_700_000_000,
            }
        )
        return PlainTextResponse("admin")

    @app.get("/set-doctor")
    def set_doctor(request: Request):
        request.session.update(
            {
                "user_id": 2,
                "login": "doctor",
                "display_name": "Лобанова",
                "role": "doctor",
                "doctor_id": 7,
                "last_seen_at": 1_700_000_000,
            }
        )
        return PlainTextResponse("doctor")

    monkeypatch.setattr(
        admin_router,
        "get_audit_event",
        lambda event_id: {
            "id": event_id,
            "created_at": None,
            "user_login": "Лобанова",
            "user_role": "doctor",
            "action": "create_appointment",
            "action_label": "Создал повторный приём",
            "result": "success",
            "result_label": "успешно",
            "patient_id": 6,
            "patient_name": "Волкова Татьяна Николаевна",
            "appointment_id": 28,
            "entity_type": "appointment",
            "entity_id": 28,
            "method": "POST",
            "path": "/api/patients/6/appointments/new",
            "status_code": 303,
            "details": "создан повторный приём",
            "error_message": None,
            "event_sentence": "пользователь Лобанова — создал повторный приём",
        },
    )
    monkeypatch.setattr(
        admin_router,
        "get_audit_event_changes",
        lambda event_id: [
            {
                "section": "biochemistry",
                "section_label": "Биохимия крови",
                "field_label": "Биохимия от 2026-07-09",
                "field_name": "biochemistry_investigation_date",
                "change_type": "lab_added",
                "change_type_label": "Добавлен анализ",
                "old_value": None,
                "new_value": "2026-07-09",
                "details": "Креатинин: 110",
            }
        ],
    )
    monkeypatch.setattr(
        admin_router,
        "group_audit_changes_by_section",
        audit_log.group_audit_changes_by_section,
    )
    monkeypatch.setattr(admin_router, "log_audit_event", lambda *args, **kwargs: 999)

    app.include_router(admin_router.router)
    return app


@pytest.fixture()
def admin_detail_client(admin_detail_app):
    with TestClient(admin_detail_app) as client:
        yield client


def test_17_admin_can_open_audit_detail_page(admin_detail_client):
    admin_detail_client.get("/set-admin")

    response = admin_detail_client.get("/admin/audit/123")

    assert response.status_code == 200
    assert "Подробности события аудита №123" in response.text
    assert "Биохимия крови" in response.text
    assert "Креатинин: 110" in response.text


def test_18_doctor_cannot_open_audit_detail_page(admin_detail_client):
    admin_detail_client.get("/set-doctor")

    response = admin_detail_client.get("/admin/audit/123")

    assert response.status_code == 403


def test_19_unknown_audit_event_returns_404(admin_detail_client, monkeypatch):
    monkeypatch.setattr(admin_router, "get_audit_event", lambda event_id: None)
    admin_detail_client.get("/set-admin")

    response = admin_detail_client.get("/admin/audit/999")

    assert response.status_code == 404
