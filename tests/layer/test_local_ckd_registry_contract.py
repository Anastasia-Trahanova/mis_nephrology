from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile
from io import BytesIO

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app.repositories import ckd_registry as registry_repository
from app.routers import ckd_registry

ROOT = Path(__file__).resolve().parents[2]


def test_registry_filters_normalize_values():
    filters = registry_repository.CkdRegistryFilters.from_mapping(
        {
            "search": " Иванова ",
            "stage": "С4",
            "outcome": "rrt_hemodialysis",
            "included_from": "2026-08-10",
            "included_to": "2026-08-01",
        }
    )
    assert filters.search == "Иванова"
    assert filters.stage == "С4"
    assert filters.outcome == "rrt_hemodialysis"
    assert filters.included_from == date(2026, 8, 1)
    assert filters.included_to == date(2026, 8, 10)


def test_registry_sql_uses_current_patient_and_latest_appointment_data():
    snapshot_sql = registry_repository._snapshot_select_sql()
    registry_sql, _ = registry_repository._registry_sql(
        registry_repository.CkdRegistryFilters()
    )
    for sql in (snapshot_sql, registry_sql):
        assert "FROM appointments" in sql
        assert "appointment_icd10_diagnoses_view" in sql
        assert "calculated_metrics" in sql
        assert "JOIN diagnoses" not in sql
        assert "LEFT JOIN diagnoses" not in sql
    assert "p.phone" in registry_sql
    assert "WHERE cm.appointment_id = a.id" in snapshot_sql
    assert "latest_appointment.egfr_ckdepi AS egfr" in snapshot_sql
    assert "latest_appointment.ckd_stage" in snapshot_sql
    assert "e.diagnosis_at_inclusion" in registry_sql
    assert "e.egfr_at_inclusion" in registry_sql
    assert "e.ckd_stage_at_inclusion" in registry_sql


def test_registry_page_and_patient_card_have_required_fields():
    page = (ROOT / "app" / "templates" / "ckd_registry.html").read_text(encoding="utf-8")
    panel = (
        ROOT / "app" / "templates" / "patient_card" / "_ckd_registry_panel.html"
    ).read_text(encoding="utf-8")
    for marker in (
        "ФИО",
        "Дата<br>рождения",
        "Дата включения<br>в регистр",
        "Телефон",
        "Основной<br>диагноз",
        "СКФ",
        "Стадия<br>ХБП",
        "Исход",
        'title="Открыть электронную медицинскую карту"',
        "Выгрузить в Excel",
    ):
        assert marker in page
    assert "Добавление пациента в регистр пациентов с ХБП" in panel
    assert "Добавить в регистр" in panel
    assert "Пациент добавлен в регистр пациентов с ХБП" in panel
    assert "Добавить исход" in panel
    assert "гарантирует их корректность" in panel
    assert 'name="phone"' in panel
    assert 'name="diagnosis"' in panel
    assert 'name="egfr"' in panel
    assert 'name="stage"' in panel
    assert 'name="outcome"' in panel
    assert 'name="comment"' in panel
    assert "СКФ по последнему приёму" in panel
    assert "Стадия ХБП по последнему приёму" in panel
    assert '<option value="observed" selected>Наблюдается</option>' in panel
    assert ">Наблюдается</option>" in page

def test_registry_navigation_and_access_are_separated_from_patient_lists():
    base = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert 'href="/patient-lists"' in base
    assert 'href="/ckd-registry"' in base
    assert "{% set management_roles = ('admin', 'chief_physician', 'department_head') %}" in base
    assert "{% if current_role in management_roles %}" in base
    assert "patient_lists.router" in main
    assert "ckd_registry.router" in main

def test_registry_page_is_management_only():
    class FakeRequest:
        def __init__(self, role):
            self.session = {"role": role}

    ckd_registry.require_ckd_registry_access(FakeRequest("chief_physician"))
    ckd_registry.require_ckd_registry_access(FakeRequest("department_head"))
    with pytest.raises(Exception) as error:
        ckd_registry.require_ckd_registry_access(FakeRequest("doctor"))
    assert getattr(error.value, "status_code", None) == 403


def test_doctor_can_submit_patient_to_registry(monkeypatch):
    captured = {}

    def fake_add(**kwargs):
        captured.update(kwargs)
        return 1

    monkeypatch.setattr(ckd_registry, "add_patient_to_registry", fake_add)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(ckd_registry.router)

    @app.get("/set-doctor")
    def set_doctor(request: Request):
        request.session.update(
            {"user_id": 17, "doctor_id": 7, "role": "doctor", "display_name": "Врач"}
        )
        return PlainTextResponse("ok")

    with TestClient(app) as client:
        client.get("/set-doctor")
        response = client.post(
            "/ckd-registry/patient/11/include",
            data={
                "last_name": "Иванова",
                "first_name": "Мария",
                "patronymic": "Петровна",
                "birth_date": "1965-03-12",
                "phone": "+7 900 000-00-00",
                "diagnosis": "N18.4 — Хроническая болезнь почек, стадия 4",
                "egfr": "24.5",
                "stage": "С4",
                "outcome": "",
                "comment": "Проверено",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/patient/11?registry_status=included")
    assert captured["patient_id"] == 11
    assert captured["user_id"] == 17
    assert captured["stage"] == "С4"


def test_xlsx_export_is_a_valid_office_archive():
    content = registry_repository._xlsx_bytes(
        [
            {
                "patient_id": 11,
                "patient_fio": "Иванова Мария Петровна",
                "birth_date": date(1965, 3, 12),
                "included_at": date(2026, 8, 1),
                "phone": "+7 900 000-00-00",
                "main_diagnosis": "N18.4 — Хроническая болезнь почек, стадия 4",
                "egfr": Decimal("24.50"),
                "ckd_stage": "С4",
                "outcome_label": "Наблюдается",
                "outcome_date": None,
            }
        ]
    )
    with ZipFile(BytesIO(content)) as archive:
        names = set(archive.namelist())
        assert "[Content_Types].xml" in names
        assert "xl/workbook.xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        assert sheet.tag.endswith("worksheet")
