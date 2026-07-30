from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app import registry_queries
from app.registry_queries import RegistryFilters, describe_filters
from app.routers import ckd_registry


ROOT = Path(__file__).resolve().parents[2]


def test_registry_filters_defaults_and_comma_decimal():
    filters = RegistryFilters.from_mapping({"indicator": "potassium", "value_from": "5,5"})
    assert filters.indicator == "potassium"
    assert filters.value_from == Decimal("5.5")
    assert filters.mode == "manual"


def test_egfr_category_boundaries_are_correct():
    assert registry_queries.EGFR_CATEGORIES["С3а"]["minimum"] == Decimal("45")
    assert registry_queries.EGFR_CATEGORIES["С3б"]["minimum"] == Decimal("30")
    assert registry_queries.EGFR_CATEGORIES["С4"]["minimum"] == Decimal("15")
    assert registry_queries.EGFR_CATEGORIES["С5"]["maximum"] == Decimal("15")


def test_manual_range_is_normalized():
    filters = RegistryFilters.from_mapping(
        {
            "indicator": "egfr",
            "mode": "manual",
            "operator": "between",
            "value_from": "35",
            "value_to": "20",
        }
    )
    assert filters.value_from == Decimal("20")
    assert filters.value_to == Decimal("35")


def test_description_explains_filter():
    filters = RegistryFilters.from_mapping(
        {"indicator": "egfr", "mode": "category", "egfr_category": "С4", "period_months": "6"}
    )
    text = describe_filters(filters)
    assert "С4 — 15–29" in text
    assert "6 месяцев" in text


def test_sql_uses_one_ranked_query_and_existing_tables():
    filters = RegistryFilters.from_mapping({"indicator": "hemoglobin"})
    sql = registry_queries._registry_sql(filters)
    assert "FROM cbc_results r" in sql
    assert "JOIN latest_value latest" in sql
    assert "COUNT(*) OVER()" in sql
    assert "LIMIT %(limit)s OFFSET %(offset)s" in sql
    assert "first_appointment_id" in sql
    assert "first_visit_value" in sql
    assert "AGE(last_visit.appointment_date, p.birth_date)" in sql


def test_template_has_dynamic_controls_and_requested_columns():
    template = (ROOT / "app" / "templates" / "ckd_registry.html").read_text(encoding="utf-8")
    assert "Списки пациентов" in template
    assert 'name="indicator"' in template
    assert 'name="egfr_category"' in template
    assert 'name="value_from"' in template
    assert "Наблюдается" in template
    assert "Возраст" in template
    assert "На первом приёме" in template
    assert "Последнее значение" in template
    assert "Открыть ЭМК" in template
    assert 'id="registrySubmitButton"' in template
    assert 'id="registryResetButton"' in template
    assert 'id="registryExportButton"' in template
    assert 'data-registry-patient-row' in template
    assert 'data-registry-open-patient' in template


def test_navigation_is_available_to_doctor_and_admin():
    base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    assert "request.session.get('role') in ('admin', 'doctor')" in base
    assert "Списки пациентов" in base
    assert "Журнал аудита" in base


def test_doctor_can_open_registry(monkeypatch):
    monkeypatch.setattr(
        ckd_registry,
        "get_patient_registry",
        lambda filters: {
            "rows": [],
            "total": 0,
            "pages": 1,
            "page": 1,
            "page_size": 25,
            "description": "тест",
            "query_without_page": "indicator=hemoglobin",
        },
    )

    app = FastAPI()
    app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(ckd_registry.router)

    @app.get("/set-doctor")
    def set_doctor(request: Request):
        request.session.update({"user_id": 7, "role": "doctor", "display_name": "Врач"})
        return PlainTextResponse("ok")

    with TestClient(app) as client:
        client.get("/set-doctor")
        response = client.get("/ckd-registry")

    assert response.status_code == 200
    assert "Списки пациентов" in response.text


def test_non_medical_role_is_rejected():
    class SessionRequest:
        session = {"role": "patient"}

    with pytest.raises(Exception) as error:
        ckd_registry.require_registry_access(SessionRequest())
    assert getattr(error.value, "status_code", None) == 403


def test_csv_contains_first_and_latest_values(monkeypatch):
    monkeypatch.setattr(
        registry_queries,
        "get_patient_registry",
        lambda filters: {
            "description": "Гемоглобин ниже 120",
            "rows": [
                {
                    "patient_fio": "Иванова Мария",
                    "birth_date": date(1965, 3, 12),
                    "gender": "Ж",
                    "observation_duration": "2 г. 3 мес.",
                    "first_visit_value": Decimal("110"),
                    "first_appointment_date": date(2024, 1, 1),
                    "latest_value": Decimal("105"),
                    "latest_value_date": date(2026, 7, 1),
                    "value_change": Decimal("-5"),
                    "has_iron_prescription": True,
                    "iron_medications": "Железо",
                    "last_appointment_date": date(2026, 7, 2),
                    "last_doctor_name": "Лобанова Н.",
                }
            ],
        },
    )
    content, filename = registry_queries.build_registry_csv(RegistryFilters())
    assert content.startswith("\ufeff")
    assert "Значение на первом приёме" in content
    assert "Последнее значение" in content
    assert "Иванова Мария" in content
    assert filename.endswith(".csv")


def test_registry_page_renders_patient_history(monkeypatch):
    monkeypatch.setattr(
        ckd_registry,
        "get_patient_registry",
        lambda filters: {
            "rows": [
                {
                    "patient_id": 11,
                    "patient_fio": "Иванова Мария Петровна",
                    "birth_date": date(1965, 3, 12),
                    "age": 61,
                    "gender": "Ж",
                    "observation_duration": "2 г. 3 мес.",
                    "first_appointment_date": date(2024, 1, 1),
                    "first_visit_value": Decimal("110"),
                    "latest_value": Decimal("105"),
                    "latest_value_date": date(2026, 7, 1),
                    "value_change": Decimal("-5"),
                    "egfr_category": None,
                    "has_iron_prescription": True,
                    "iron_medications": "Железо",
                    "last_appointment_date": date(2026, 7, 2),
                    "last_doctor_name": "Лобанова Н.",
                }
            ],
            "total": 1,
            "pages": 1,
            "page": 1,
            "page_size": 25,
            "description": "Гемоглобин ниже 120",
            "query_without_page": "indicator=hemoglobin",
        },
    )

    app = FastAPI()
    app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(ckd_registry.router)

    @app.get("/set-doctor")
    def set_doctor(request: Request):
        request.session.update({"user_id": 7, "role": "doctor", "display_name": "Врач"})
        return PlainTextResponse("ok")

    with TestClient(app) as client:
        client.get("/set-doctor")
        response = client.get("/ckd-registry")

    assert response.status_code == 200
    assert "Иванова Мария Петровна" in response.text
    assert "2 г. 3 мес." in response.text
    assert "110" in response.text
    assert "105" in response.text
    assert "Железо" in response.text


def test_registry_export_route_is_available_to_doctor(monkeypatch):
    monkeypatch.setattr(
        ckd_registry,
        "build_registry_csv",
        lambda filters: ("\ufeffФИО;Показатель\r\nИванова;105\r\n", "patient_lists.csv"),
    )

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(ckd_registry.router)

    @app.get("/set-doctor")
    def set_doctor(request: Request):
        request.session.update({"user_id": 7, "role": "doctor"})
        return PlainTextResponse("ok")

    with TestClient(app) as client:
        client.get("/set-doctor")
        response = client.get("/ckd-registry/export.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "patient_lists.csv" in response.headers["content-disposition"]
    assert response.content.startswith("\ufeff".encode("utf-8"))


@pytest.mark.parametrize(
    ("indicator", "table_name", "column_name"),
    [
        ("hemoglobin", "cbc_results", "hemoglobin"),
        ("potassium", "biochemistry_results", "potassium"),
        ("ptg", "biochemistry_results", "ptg"),
        ("egfr", "calculated_metrics", "egfr_ckdepi"),
    ],
)
def test_each_indicator_uses_whitelisted_source(indicator, table_name, column_name):
    filters = RegistryFilters.from_mapping({"indicator": indicator})
    sql = registry_queries._registry_sql(filters)
    assert f"FROM {table_name} r" in sql
    assert f"r.{column_name}" in sql


def test_csv_escapes_formula_like_text(monkeypatch):
    monkeypatch.setattr(
        registry_queries,
        "get_patient_registry",
        lambda filters: {
            "description": "Гемоглобин ниже 120",
            "rows": [
                {
                    "patient_fio": "=HYPERLINK(\"https://example.test\")",
                    "birth_date": date(1965, 3, 12),
                    "gender": "Ж",
                    "observation_duration": "2 г.",
                    "first_visit_value": Decimal("110"),
                    "first_appointment_date": date(2024, 1, 1),
                    "latest_value": Decimal("105"),
                    "latest_value_date": date(2026, 7, 1),
                    "value_change": Decimal("-5"),
                    "has_iron_prescription": False,
                    "iron_medications": "",
                    "last_appointment_date": date(2026, 7, 2),
                    "last_doctor_name": "@doctor",
                }
            ],
        },
    )
    content, _ = registry_queries.build_registry_csv(RegistryFilters())
    assert "'=HYPERLINK" in content
    assert "'@doctor" in content


def test_registry_hotkeys_cover_page_actions():
    script = (ROOT / "app" / "static" / "js" / "patient_lists.js").read_text(encoding="utf-8")
    base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")

    assert 'code === "Enter"' in script
    assert 'form.requestSubmit(submitButton || undefined)' in script
    assert 'code === "KeyR"' in script
    assert 'code === "KeyC"' in script
    assert 'code === "KeyO"' in script
    assert 'code === "ArrowLeft"' in script
    assert 'code === "ArrowRight"' in script
    assert 'code === "ArrowUp" || code === "ArrowDown"' in script
    assert "is_registry_page" in base
    assert "Открыть ЭМК выбранного пациента" in base
