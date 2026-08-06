from __future__ import annotations

"""Отчёт по лабораторным результатам без единиц измерения.

Скрипт читает только SQLite парсера и не изменяет ни SQLite, ни PostgreSQL.
"""

import argparse
import csv
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


CLEAN_STATUS = "ЧИСТАЯ_ЗАПИСЬ"


class ReportError(RuntimeError):
    pass


@dataclass
class SummaryRow:
    study_type: str
    indicator_normalized: str
    count: int = 0
    raw_names: set[str] = field(default_factory=set)
    values: list[str] = field(default_factory=list)


def resolve_source(path: Path) -> Path:
    candidate = path.expanduser()
    if candidate.is_dir():
        candidate = candidate / "приемы.sqlite"
    candidate = candidate.resolve()
    if not candidate.is_file():
        raise ReportError(f"Не найден SQLite: {candidate}")
    return candidate


def default_source(project_root: Path) -> Path:
    return (
        project_root.parent
        / "nephro_consultation_preparer"
        / "prepared_consultations"
        / "приемы.sqlite"
    )


def ensure_schema(connection: sqlite3.Connection) -> None:
    required = {
        "laboratory_results": {
            "consultation_id",
            "study_type",
            "indicator_raw",
            "indicator_normalized",
            "numeric_value",
            "text_value",
            "unit",
            "source_text",
            "analysis_date",
        },
        "consultations": {
            "consultation_id",
            "resolved_name",
            "appointment_date",
            "status",
        },
    }
    for table, columns in required.items():
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {str(row[1]) for row in rows}
        missing = columns - existing
        if missing:
            raise ReportError(
                f"В таблице {table} отсутствуют поля: {', '.join(sorted(missing))}"
            )


def collect_rows(connection: sqlite3.Connection, include_text: bool = False):
    condition = "lr.numeric_value IS NOT NULL AND trim(lr.numeric_value) <> ''"
    if include_text:
        condition = (
            "((lr.numeric_value IS NOT NULL AND trim(lr.numeric_value) <> '') "
            "OR (lr.text_value IS NOT NULL AND trim(lr.text_value) <> ''))"
        )
    return connection.execute(
        f"""
        SELECT
            lr.consultation_id,
            c.resolved_name,
            c.appointment_date,
            lr.analysis_date,
            lr.study_type,
            lr.indicator_raw,
            lr.indicator_normalized,
            lr.numeric_value,
            lr.text_value,
            lr.source_text
        FROM laboratory_results lr
        JOIN consultations c ON c.consultation_id = lr.consultation_id
        WHERE c.status = ?
          AND trim(COALESCE(lr.unit, '')) = ''
          AND {condition}
        ORDER BY lr.study_type, lr.indicator_normalized, lr.consultation_id
        """,
        (CLEAN_STATUS,),
    ).fetchall()


def build_summary(rows) -> list[SummaryRow]:
    grouped: dict[tuple[str, str], SummaryRow] = {}
    for row in rows:
        study_type = str(row[4] or "Не указан").strip() or "Не указан"
        indicator = str(row[6] or row[5] or "Не указан").strip() or "Не указан"
        key = (study_type, indicator)
        item = grouped.setdefault(key, SummaryRow(study_type, indicator))
        item.count += 1
        raw = str(row[5] or "").strip()
        if raw:
            item.raw_names.add(raw)
        value = str(row[7] or row[8] or "").strip()
        if value and value not in item.values and len(item.values) < 8:
            item.values.append(value)
    return sorted(
        grouped.values(),
        key=lambda item: (-item.count, item.study_type, item.indicator_normalized),
    )


def write_reports(rows, summary: list[SummaryRow], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")

    summary_path = output_dir / "labs_without_units_summary.csv"
    details_path = output_dir / "labs_without_units_details.csv"

    with summary_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(
            [
                "Вид исследования",
                "Показатель",
                "Количество без единицы",
                "Названия в исходниках",
                "Примеры значений",
            ]
        )
        for item in summary:
            writer.writerow(
                [
                    item.study_type,
                    item.indicator_normalized,
                    item.count,
                    " | ".join(sorted(item.raw_names)[:12]),
                    " | ".join(item.values),
                ]
            )

    with details_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(
            [
                "ID консультации",
                "Пациент",
                "Дата приёма",
                "Дата анализа",
                "Вид исследования",
                "Название в исходнике",
                "Нормализованное название",
                "Числовое значение",
                "Текстовое значение",
                "Исходный фрагмент",
            ]
        )
        writer.writerows(rows)

    return summary_path, details_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Найти лабораторные результаты без единиц измерения"
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Путь к приемы.sqlite или папке prepared_consultations",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("local_reports"),
        help="Локальная папка отчётов; по умолчанию local_reports",
    )
    parser.add_argument(
        "--include-text",
        action="store_true",
        help="Включить также текстовые результаты без единиц",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_root = Path(__file__).resolve().parents[1]
    source = resolve_source(args.source or default_source(project_root))
    output_dir = args.output_dir.expanduser()
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    connection = sqlite3.connect(source)
    try:
        ensure_schema(connection)
        rows = collect_rows(connection, include_text=args.include_text)
    finally:
        connection.close()

    summary = build_summary(rows)
    summary_path, details_path = write_reports(rows, summary, output_dir.resolve())

    print(f"Источник: {source}")
    print(f"Результатов без единицы: {len(rows)}")
    print(f"Уникальных сочетаний исследование + показатель: {len(summary)}")
    print()
    for item in summary:
        print(f"{item.study_type} | {item.indicator_normalized}: {item.count}")
    print()
    print(f"Сводка: {summary_path}")
    print(f"Детали: {details_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReportError as exc:
        print(f"ОШИБКА: {exc}")
        raise SystemExit(1) from exc
