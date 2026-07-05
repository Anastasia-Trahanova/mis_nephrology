"""
Назначение файла: второй этап разделения app/database.py.

Что делает скрипт:
- ищет в app/*.py импорты из app.database / ..database / .database;
- заменяет их на прямые импорты из новых модулей:
  app.db.connection, app.repositories.*, app.services.*;
- оставляет сам app/database.py как фасад совместимости для старых внешних
  импортов и редких переходных мест;
- не меняет SQL-запросы, медицинскую логику, шаблоны и миграции.

Зачем это нужно:
первый этап уже разнёс функции по новым файлам, но роуты и сервисы могли
продолжать импортировать всё через app.database. После этого скрипта новые
модули становятся реальным рабочим слоем приложения.

Что можно редактировать:
- IMPORT_TARGETS, если новая функция переехала в другой модуль;
- EXCLUDED_FILES, если какой-то файл надо временно оставить на фасаде.

Что не нужно редактировать здесь:
- тексты SQL-запросов;
- валидацию форм;
- расчёты СКФ/ACR/прогноза ХБП;
- инструкции по БД.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"

# Сам фасад app/database.py не переписываем, иначе потеряем совместимость.
EXCLUDED_FILES = {
    APP_DIR / "database.py",
}

# Единая карта: имя функции/объекта -> новый модуль, где оно реально живёт.
IMPORT_TARGETS = {
    # app/db/connection.py
    "DATABASE_URL": "app.db.connection",
    "DB_POOL_MIN_CONN": "app.db.connection",
    "DB_POOL_MAX_CONN": "app.db.connection",
    "PooledConnection": "app.db.connection",
    "get_db_connection": "app.db.connection",

    # app/repositories/patients.py
    "create_patient": "app.repositories.patients",
    "get_patient_for_appointment": "app.repositories.patients",
    "get_all_patients": "app.repositories.patients",
    "get_patient_by_id": "app.repositories.patients",
    "get_patient_contact_info": "app.repositories.patients",
    "_fetch_patient_by_id": "app.repositories.patients",

    # app/repositories/appointments.py
    "create_appointment": "app.repositories.appointments",
    "get_all_appointments": "app.repositories.appointments",
    "get_patient_appointments": "app.repositories.appointments",
    "get_appointment_full_data": "app.repositories.appointments",
    "get_last_appointment_data": "app.repositories.appointments",
    "get_appointment_medications": "app.repositories.appointments",
    "get_appointment_diet": "app.repositories.appointments",
    "_fetch_patient_appointments": "app.repositories.appointments",
    "_fetch_appointment_full_data": "app.repositories.appointments",
    "_fetch_last_appointment_data": "app.repositories.appointments",
    "_fetch_appointment_medications": "app.repositories.appointments",
    "_fetch_appointment_diet": "app.repositories.appointments",

    # app/repositories/reference_data.py
    "get_branches": "app.repositories.reference_data",
    "get_locations_by_branch": "app.repositories.reference_data",
    "get_doctors": "app.repositories.reference_data",
    "get_doctors_for_filter": "app.repositories.reference_data",
    "get_locations_for_filter": "app.repositories.reference_data",
    "get_doctor_locations": "app.repositories.reference_data",
    "get_location_info": "app.repositories.reference_data",
    "get_icd10_diagnoses": "app.repositories.reference_data",
    "get_appointment_icd10_diagnoses": "app.repositories.reference_data",
    "get_medications_dictionary": "app.repositories.reference_data",
    "_fetch_branches": "app.repositories.reference_data",
    "_fetch_locations_by_branch": "app.repositories.reference_data",
    "_fetch_doctors": "app.repositories.reference_data",
    "_fetch_icd10_diagnoses": "app.repositories.reference_data",
    "_fetch_appointment_icd10_diagnoses": "app.repositories.reference_data",
    "_fetch_medications_dictionary": "app.repositories.reference_data",

    # app/repositories/lab_history.py
    "get_patient_biochemistry_history": "app.repositories.lab_history",
    "get_patient_cbc_history": "app.repositories.lab_history",
    "get_patient_urinalysis_history": "app.repositories.lab_history",
    "get_patient_metrics_history": "app.repositories.lab_history",
    "get_patient_ultrasound_history": "app.repositories.lab_history",
    "get_patient_albuminuria_history": "app.repositories.lab_history",
    "save_calculated_metrics": "app.repositories.lab_history",
    "_fetch_patient_biochemistry_history": "app.repositories.lab_history",
    "_fetch_patient_cbc_history": "app.repositories.lab_history",
    "_fetch_patient_urinalysis_history": "app.repositories.lab_history",
    "_fetch_patient_metrics_history": "app.repositories.lab_history",
    "_fetch_patient_ultrasound_history": "app.repositories.lab_history",
    "_fetch_patient_albuminuria_history": "app.repositories.lab_history",

    # app/repositories/ckd_prognosis.py
    "save_ckd_prognosis_for_appointment": "app.repositories.ckd_prognosis",
    "recalculate_ckd_prognosis_for_appointment": "app.repositories.ckd_prognosis",
    "get_appointment_ckd_prognosis": "app.repositories.ckd_prognosis",
    "get_patient_ckd_prognosis_history": "app.repositories.ckd_prognosis",
    "_fetch_appointment_ckd_prognosis": "app.repositories.ckd_prognosis",
    "_fetch_patient_ckd_prognosis_history": "app.repositories.ckd_prognosis",
    "_fetch_latest_gfr_category_for_prognosis": "app.repositories.ckd_prognosis",
    "_fetch_latest_albuminuria_category_for_prognosis": "app.repositories.ckd_prognosis",

    # app/services/*.py
    "get_patient_card_context": "app.services.patient_card_context_service",
    "get_new_appointment_context": "app.services.appointment_form_context_service",
    "get_new_patient_context": "app.services.appointment_form_context_service",
    "_group_icd10_diagnoses_for_form": "app.services.appointment_form_context_service",
}

MULTILINE_IMPORT_RE = re.compile(
    r"^from\s+(?:app\.database|\.+database)\s+import\s*\((?P<body>.*?)\)\s*$",
    re.MULTILINE | re.DOTALL,
)

SINGLELINE_IMPORT_RE = re.compile(
    r"^from\s+(?:app\.database|\.+database)\s+import\s+(?P<body>[^\n]+)$",
    re.MULTILINE,
)

DIRECT_DATABASE_IMPORT_RE = re.compile(
    r"^import\s+app\.database(?:\s+as\s+\w+)?\s*$",
    re.MULTILINE,
)


def _strip_inline_comment(text: str) -> str:
    """Убирает комментарий в строке импорта, не трогая сами имена."""
    return text.split("#", 1)[0].strip()


def _parse_imported_names(body: str) -> list[str]:
    """Разбирает список импортируемых имён из блока import."""
    names: list[str] = []

    for raw_part in body.replace("\n", ",").split(","):
        part = _strip_inline_comment(raw_part)
        if not part:
            continue
        names.append(part)

    return names


def _base_name(import_item: str) -> str:
    """Возвращает исходное имя до возможного alias: name as alias -> name."""
    return import_item.split(" as ", 1)[0].strip()


def _build_replacement(import_items: list[str], source_path: Path) -> str:
    """Строит новые import-блоки по модулям назначения."""
    grouped: OrderedDict[str, list[str]] = OrderedDict()
    unknown: list[str] = []

    for item in import_items:
        name = _base_name(item)
        module = IMPORT_TARGETS.get(name)
        if not module:
            unknown.append(item)
            continue
        grouped.setdefault(module, []).append(item)

    if unknown:
        unknown_text = ", ".join(unknown)
        raise RuntimeError(
            f"Не знаю, куда перенести импорт(ы) из {source_path}: {unknown_text}. "
            "Добавь их в IMPORT_TARGETS или перенеси вручную."
        )

    blocks: list[str] = []
    for module, names in grouped.items():
        if len(names) == 1:
            blocks.append(f"from {module} import {names[0]}")
            continue

        joined = "\n".join(f"    {name}," for name in names)
        blocks.append(f"from {module} import (\n{joined}\n)")

    return "\n".join(blocks)


def _replace_database_imports(content: str, path: Path) -> tuple[str, int]:
    """Заменяет все from app.database / from ..database import ... в одном файле."""
    replacements = 0

    def replace_multiline(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        names = _parse_imported_names(match.group("body"))
        return _build_replacement(names, path)

    content = MULTILINE_IMPORT_RE.sub(replace_multiline, content)

    def replace_singleline(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        names = _parse_imported_names(match.group("body"))
        return _build_replacement(names, path)

    content = SINGLELINE_IMPORT_RE.sub(replace_singleline, content)

    if DIRECT_DATABASE_IMPORT_RE.search(content):
        raise RuntimeError(
            f"В {path} найден прямой import app.database. "
            "Такой импорт надо заменить вручную на конкретный модуль."
        )

    return content, replacements


def main() -> None:
    changed_files: list[Path] = []
    total_replacements = 0

    for path in sorted(APP_DIR.rglob("*.py")):
        if path in EXCLUDED_FILES:
            continue

        content = path.read_text(encoding="utf-8")
        new_content, replacements = _replace_database_imports(content, path)

        if replacements:
            path.write_text(new_content, encoding="utf-8")
            changed_files.append(path.relative_to(PROJECT_ROOT))
            total_replacements += replacements

    if not changed_files:
        print("OK: прямых импортов из app.database в app/*.py не найдено.")
        return

    print("OK: импорты из app.database заменены на прямые модули.")
    print(f"Заменено import-блоков: {total_replacements}")
    for path in changed_files:
        print(f"- {path}")


if __name__ == "__main__":
    main()
