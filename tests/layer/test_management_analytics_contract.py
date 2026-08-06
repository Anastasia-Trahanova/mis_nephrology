from __future__ import annotations

import io
import zipfile
from pathlib import Path

from app.services.simple_xlsx import XlsxSheet, build_xlsx

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_analytics_router_is_connected_and_named_in_navbar():
    main = read("app/main.py")
    base = read("app/templates/base.html")
    assert "management_analytics" in main
    assert "app.include_router(management_analytics.router" in main
    assert 'href="/analytics" title="Аналитика"' in base
    assert '<span class="app-sidebar__label">Аналитика</span>' in base
    assert "chief_physician" in base
    assert "department_head" in base
    assert "current_role == 'admin'" in base

def test_page_contains_only_requested_dashboard_sections():
    template = read("app/templates/management_analytics.html")

    for text in (
        "Записей в расписании",
        "Проведено приёмов",
        "Врачей с приёмами",
        "Неявок",
        "Загрузка отделений",
        "Статусы записей в расписании",
        "Нагрузка по врачам",
        "Сводка по отделениям",
    ):
        assert text in template
    assert "Детальные записи расписания" not in template
    assert "Уникальных пациентов" not in template
    assert "Топ врачей" not in template


def test_access_and_exports_are_declared():
    router = read("app/routers/management_analytics.py")
    service = read("app/services/management_analytics_service.py")

    for role in ("ROLE_ADMIN", "ROLE_CHIEF_PHYSICIAN", "ROLE_DEPARTMENT_HEAD"):
        assert role in router
    for report in ("all", "doctors", "departments", "statuses", "issues"):
        assert f'"{report}"' in service
    assert 'media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"' in router


def test_queries_use_existing_appointments_and_schedule_tables():
    repository = read("app/repositories/management_analytics.py")

    assert "FROM appointments" in repository
    assert "FROM schedule_entries" in repository
    assert "appointment_id IS NOT NULL" in repository
    assert "actual_doctor_id" in repository
    assert "appointment_type" in repository
    assert "status = 'no_show'" in repository


def test_dependency_free_xlsx_is_a_valid_zip_package():
    content = build_xlsx(
        [
            XlsxSheet(
                name="Сводка",
                title="Аналитика",
                metadata=[("Период", "01.08.2026 — 31.08.2026")],
                headers=["Показатель", "Значение"],
                rows=[["Приёмы", 36]],
            )
        ]
    )

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = set(archive.namelist())
    assert "xl/workbook.xml" in names
    assert "xl/worksheets/sheet1.xml" in names
    assert "xl/styles.xml" in names


def test_all_departments_and_all_doctors_are_optional_filters():
    template = read("app/templates/management_analytics.html")
    repository = read("app/repositories/management_analytics.py")

    assert 'name="analytics_location_id"' in template
    assert 'name="analytics_doctor_id"' in template
    assert 'name="location_id"' not in template
    assert 'name="doctor_id"' not in template
    assert 'values.get("analytics_location_id", values.get("location_id"))' in repository
    assert 'values.get("analytics_doctor_id", values.get("doctor_id"))' in repository
