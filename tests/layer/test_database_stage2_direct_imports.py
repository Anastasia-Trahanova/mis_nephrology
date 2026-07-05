"""
Назначение файла: проверка второго этапа разделения database.py.

Что проверяет:
- роуты и сервисы больше не импортируют функции через app.database;
- app/database.py остаётся только фасадом совместимости;
- ключевые функции доступны из новых прямых модулей;
- важные файлы действительно переключены на новые app.repositories/app.services.

Этот тест не подключается к реальной БД. Он проверяет структуру импортов и
наличие функций, поэтому безопасен для обычного layer-запуска.
"""

from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app"

FORBIDDEN_IMPORT_SNIPPETS = [
    "from app.database import",
    "from ..database import",
    "from .database import",
    "import app.database",
]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_app_files_do_not_import_database_facade_directly():
    """После второго этапа app-код должен использовать прямые модули."""
    offenders: list[str] = []

    for path in sorted(APP_DIR.rglob("*.py")):
        if path.name == "database.py":
            continue

        content = path.read_text(encoding="utf-8")
        if any(snippet in content for snippet in FORBIDDEN_IMPORT_SNIPPETS):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_pages_router_uses_context_services_and_repositories():
    """pages.py должен брать context из сервисов, а SQL-чтение из repositories."""
    content = _read("app/routers/pages.py")

    assert "from app.services.patient_card_context_service import get_patient_card_context" in content
    assert "from app.services.appointment_form_context_service import" in content
    assert "from app.repositories.reference_data import" in content
    assert "from app.repositories.lab_history import" in content
    assert "from app.repositories.ckd_prognosis import" in content
    assert "from app.database import" not in content
    assert "from ..database import" not in content


def test_filter_router_uses_reference_data_and_appointment_repository():
    """Фильтры главной страницы не должны идти через app.database."""
    content = _read("app/routers/appointment_filters.py")

    assert "from app.repositories.appointments import get_all_appointments" in content
    assert "from app.repositories.reference_data import" in content
    assert "from app.database import" not in content
    assert "from ..database import" not in content


def test_services_use_connection_and_ckd_repository_directly():
    """Сервисы сохранения должны обращаться к connection/ckd_prognosis напрямую."""
    patient_service = _read("app/services/patient_appointment_service.py")
    save_service = _read("app/services/appointment_save_service.py")

    assert "from app.db.connection import get_db_connection" in patient_service
    assert "from app.repositories.ckd_prognosis import save_ckd_prognosis_for_appointment" in save_service
    assert "from ..database import" not in patient_service
    assert "from ..database import" not in save_service


def test_auth_uses_connection_module_directly():
    """Авторизация использует только техническое подключение, а не весь фасад database.py."""
    content = _read("app/routers/auth.py")

    assert "from app.db.connection import get_db_connection" in content
    assert "from ..database import get_db_connection" not in content


def test_database_facade_still_exports_legacy_names():
    """Фасад app.database оставлен для совместимости и старых внешних импортов."""
    database = importlib.import_module("app.database")

    for name in [
        "get_db_connection",
        "get_patient_card_context",
        "get_new_appointment_context",
        "get_new_patient_context",
        "get_all_patients",
        "get_all_appointments",
        "get_patient_biochemistry_history",
        "save_ckd_prognosis_for_appointment",
    ]:
        assert hasattr(database, name), name


def test_new_repository_modules_export_expected_functions():
    """Ключевые функции должны быть доступны из новых целевых модулей."""
    checks = {
        "app.db.connection": ["get_db_connection"],
        "app.repositories.reference_data": ["get_branches", "get_doctors", "get_location_info"],
        "app.repositories.patients": ["get_all_patients", "get_patient_by_id", "get_patient_contact_info"],
        "app.repositories.appointments": ["get_all_appointments", "get_appointment_full_data"],
        "app.repositories.lab_history": ["get_patient_cbc_history", "get_patient_biochemistry_history"],
        "app.repositories.ckd_prognosis": ["get_appointment_ckd_prognosis", "save_ckd_prognosis_for_appointment"],
        "app.services.patient_card_context_service": ["get_patient_card_context"],
        "app.services.appointment_form_context_service": ["get_new_patient_context", "get_new_appointment_context"],
    }

    for module_name, names in checks.items():
        module = importlib.import_module(module_name)
        for name in names:
            assert hasattr(module, name), f"{module_name}.{name}"
