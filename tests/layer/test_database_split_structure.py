"""
Назначение файла: structural tests для разнесения app/database.py.

Эти тесты не подключаются к PostgreSQL и не меняют данные. Они проверяют,
что после рефакторинга появились понятные модули, а старый app/database.py
остался фасадом совместимости.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


EXPECTED_FILES = [
    "app/db/connection.py",
    "app/db/README.md",
    "app/repositories/reference_data.py",
    "app/repositories/patients.py",
    "app/repositories/appointments.py",
    "app/repositories/lab_history.py",
    "app/repositories/ckd_prognosis.py",
    "app/services/patient_card_context_service.py",
    "app/services/appointment_form_context_service.py",
]


def test_database_split_files_exist():
    for relative_path in EXPECTED_FILES:
        assert (ROOT / relative_path).exists(), relative_path


def test_new_modules_have_human_descriptions():
    for relative_path in EXPECTED_FILES:
        if not relative_path.endswith(".py"):
            continue

        content = (ROOT / relative_path).read_text(encoding="utf-8")

        assert "Назначение файла" in content
        assert "Что редактировать" in content or "Что выполняет файл" in content


def test_database_py_is_compatibility_facade():
    content = (ROOT / "app" / "database.py").read_text(encoding="utf-8")

    assert "фасад совместимости" in content
    assert "from app.db.connection import" in content
    assert "from app.repositories.reference_data import" in content
    assert "from app.repositories.patients import" in content
    assert "from app.repositories.appointments import" in content
    assert "from app.repositories.lab_history import" in content
    assert "from app.repositories.ckd_prognosis import" in content
    assert "from app.services.patient_card_context_service import" in content
    assert "from app.services.appointment_form_context_service import" in content

    # В фасаде не должны жить прямые SQL-блоки.
    assert "cur.execute(" not in content
    assert "ThreadedConnectionPool(" not in content
