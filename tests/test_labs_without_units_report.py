from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "report_labs_without_units.py"
SPEC = importlib.util.spec_from_file_location("lab_unit_report", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def build_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE consultations (
            consultation_id TEXT PRIMARY KEY,
            resolved_name TEXT,
            appointment_date TEXT,
            status TEXT
        );
        CREATE TABLE laboratory_results (
            consultation_id TEXT,
            analysis_date TEXT,
            study_type TEXT,
            indicator_raw TEXT,
            indicator_normalized TEXT,
            numeric_value TEXT,
            text_value TEXT,
            unit TEXT,
            source_text TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO consultations VALUES (?, ?, ?, ?)",
        ("C1", "Иванова Анна", "2024-01-01", "ЧИСТАЯ_ЗАПИСЬ"),
    )
    connection.execute(
        "INSERT INTO consultations VALUES (?, ?, ?, ?)",
        ("C2", "Петров Пётр", "2024-01-02", "ТРЕБУЕТ_ПРОВЕРКИ"),
    )
    connection.executemany(
        "INSERT INTO laboratory_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("C1", "2023-12-01", "Биохимия", "креатинин", "Креатинин", "120", None, None, "Креатинин 120"),
            ("C1", "2023-12-01", "Биохимия", "мочевина", "Мочевина", "8.1", None, "ммоль/л", "Мочевина 8.1 ммоль/л"),
            ("C1", "2023-12-01", "ОАМ", "цвет", "Цвет", None, "желтый", None, "Цвет желтый"),
            ("C2", "2023-12-01", "Биохимия", "креатинин", "Креатинин", "130", None, None, "Креатинин 130"),
        ],
    )
    connection.commit()
    return connection


def test_report_selects_clean_numeric_rows_without_units(tmp_path: Path):
    connection = build_db(tmp_path / "source.sqlite")
    try:
        MODULE.ensure_schema(connection)
        rows = MODULE.collect_rows(connection)
    finally:
        connection.close()

    assert len(rows) == 1
    assert rows[0][6] == "Креатинин"
    summary = MODULE.build_summary(rows)
    assert len(summary) == 1
    assert summary[0].count == 1
    assert summary[0].values == ["120"]


def test_report_writes_git_ignored_local_files(tmp_path: Path):
    connection = build_db(tmp_path / "source.sqlite")
    try:
        rows = MODULE.collect_rows(connection)
    finally:
        connection.close()
    summary = MODULE.build_summary(rows)
    summary_path, details_path = MODULE.write_reports(rows, summary, tmp_path / "reports")

    assert summary_path.is_file()
    assert details_path.is_file()
    assert (tmp_path / "reports" / ".gitignore").read_text(encoding="utf-8") == "*\n!.gitignore\n"
