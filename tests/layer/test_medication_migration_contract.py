# Проверяет согласованность итоговых SQL-файлов базы 2.0 с рабочими группами терапии.

from __future__ import annotations

import re
from pathlib import Path

from app.medication_therapy import MEDICATION_THERAPY_GROUPS


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = ROOT / "database" / "01 создание таблиц.sql"
CONSTRAINTS_SQL = ROOT / "database" / "02 настройка связей ключей и ограничений.sql"
DICTIONARY_SQL = ROOT / "database" / "03 заполнение справочников МКБ и лекарств.sql"


def test_final_schema_groups_match_runtime_groups_exactly():
    schema = SCHEMA_SQL.read_text(encoding="utf-8")
    constraints = CONSTRAINTS_SQL.read_text(encoding="utf-8")
    runtime_groups = tuple(group["value"] for group in MEDICATION_THERAPY_GROUPS)

    assert "therapy_group VARCHAR(64)" in schema
    assert "ck_prescriptions_therapy_group" in constraints
    for group in runtime_groups:
        assert f"'{group}'" in constraints


def test_final_dictionary_matches_unique_runtime_suggestions():
    sql = DICTIONARY_SQL.read_text(encoding="utf-8")
    medication_insert = re.search(
        r"INSERT INTO medications\s*\([^;]+?\)\s*VALUES\s*(.+?);",
        sql,
        flags=re.DOTALL,
    )
    assert medication_insert is not None

    seeded_names = re.findall(
        r"^\s*\('([^']+)'\s*,",
        medication_insert.group(1),
        flags=re.MULTILINE,
    )
    runtime_names = {
        name
        for group in MEDICATION_THERAPY_GROUPS
        for name in group["medications"]
    }

    assert len(seeded_names) == 27
    assert len(set(seeded_names)) == 27
    assert set(seeded_names) == runtime_names


def test_every_runtime_group_and_medication_is_complete():
    values = [group["value"] for group in MEDICATION_THERAPY_GROUPS]
    assert len(values) == len(set(values)) == 5

    for group in MEDICATION_THERAPY_GROUPS:
        assert group["code"].strip()
        assert group["value"].strip()
        assert group["title"].strip()
        assert group["medications"]
        assert all(name.strip() for name in group["medications"])
