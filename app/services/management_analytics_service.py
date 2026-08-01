"""Подготовка данных дашборда и Excel-отчётов административной аналитики."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from app.repositories.management_analytics import (
    AnalyticsFilters,
    get_analytics_filter_options,
    get_appointment_department_stats,
    get_appointment_doctor_stats,
    get_appointment_summary,
    get_schedule_department_stats,
    get_schedule_doctor_stats,
    get_schedule_statuses,
    get_schedule_summary,
)
from app.services.simple_xlsx import XlsxSheet, build_xlsx

REPORT_LABELS = {
    "all": "Общий аналитический отчёт",
    "doctors": "Нагрузка по врачам",
    "departments": "Сводка по отделениям",
    "statuses": "Расписание и статусы",
    "issues": "Неявки и отмены",
}


def _number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _percent(part: int, total: int) -> float:
    return round(part * 100 / total, 1) if total else 0.0


def _average(total: int, days: int) -> float:
    return round(total / days, 1) if days else 0.0


def _merge_departments(
    appointment_rows: list[dict[str, Any]],
    schedule_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[int, dict[str, Any]] = {}
    for source in appointment_rows:
        item = dict(source)
        location_id = int(item["location_id"])
        completed = _number(item.get("completed_count"))
        active_days = _number(item.get("active_days"))
        merged[location_id] = {
            **item,
            "location_id": location_id,
            "completed_count": completed,
            "doctors_count": _number(item.get("doctors_count")),
            "active_days": active_days,
            "primary_count": _number(item.get("primary_count")),
            "repeat_count": _number(item.get("repeat_count")),
            "schedule_count": 0,
            "no_show_count": 0,
            "cancelled_count": 0,
            "average_per_day": _average(completed, active_days),
        }
    for source in schedule_rows:
        location_id = int(source["location_id"])
        item = merged.setdefault(
            location_id,
            {
                "location_id": location_id,
                "location_name": source.get("location_name") or "Отделение",
                "display_name": source.get("display_name") or source.get("location_name") or "Отделение",
                "completed_count": 0,
                "doctors_count": 0,
                "active_days": 0,
                "primary_count": 0,
                "repeat_count": 0,
                "average_per_day": 0.0,
            },
        )
        item["schedule_count"] = _number(source.get("schedule_count"))
        item["no_show_count"] = _number(source.get("no_show_count"))
        item["cancelled_count"] = _number(source.get("cancelled_count"))
    for item in merged.values():
        item["no_show_rate"] = _percent(item.get("no_show_count", 0), item.get("schedule_count", 0))
    rows = sorted(
        merged.values(),
        key=lambda row: (-row.get("completed_count", 0), str(row.get("display_name") or "")),
    )
    maximum = max((row.get("completed_count", 0) for row in rows), default=0)
    for row in rows:
        row["chart_percent"] = round(row.get("completed_count", 0) * 100 / maximum, 1) if maximum else 0.0
    return rows


def _merge_doctors(
    appointment_rows: list[dict[str, Any]],
    schedule_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[tuple[int, int], dict[str, Any]] = {}
    for source in appointment_rows:
        key = (int(source["doctor_id"]), int(source["location_id"]))
        completed = _number(source.get("completed_count"))
        active_days = _number(source.get("active_days"))
        merged[key] = {
            **dict(source),
            "doctor_id": key[0],
            "location_id": key[1],
            "completed_count": completed,
            "active_days": active_days,
            "primary_count": _number(source.get("primary_count")),
            "repeat_count": _number(source.get("repeat_count")),
            "schedule_count": 0,
            "no_show_count": 0,
            "cancelled_count": 0,
            "average_per_day": _average(completed, active_days),
        }
    for source in schedule_rows:
        key = (int(source["doctor_id"]), int(source["location_id"]))
        item = merged.setdefault(
            key,
            {
                **dict(source),
                "doctor_id": key[0],
                "location_id": key[1],
                "completed_count": 0,
                "active_days": 0,
                "primary_count": 0,
                "repeat_count": 0,
                "average_per_day": 0.0,
            },
        )
        item["schedule_count"] = _number(source.get("schedule_count"))
        item["no_show_count"] = _number(source.get("no_show_count"))
        item["cancelled_count"] = _number(source.get("cancelled_count"))

    department_values: dict[int, list[float]] = defaultdict(list)
    for item in merged.values():
        if item.get("active_days", 0):
            department_values[int(item["location_id"])].append(float(item["average_per_day"]))
    department_averages = {
        location_id: sum(values) / len(values)
        for location_id, values in department_values.items()
        if values
    }

    for item in merged.values():
        item["no_show_rate"] = _percent(item.get("no_show_count", 0), item.get("schedule_count", 0))
        department_average = department_averages.get(int(item["location_id"]), 0.0)
        item["department_average"] = round(department_average, 1)
        if not item.get("active_days") or department_average <= 0:
            item["load_label"] = "Недостаточно данных"
            item["load_class"] = "insufficient"
            item["load_ratio"] = None
        else:
            ratio = float(item["average_per_day"]) / department_average
            item["load_ratio"] = round(ratio * 100)
            if ratio > 1.2:
                item["load_label"] = "Выше средней"
                item["load_class"] = "high"
            elif ratio < 0.8:
                item["load_label"] = "Ниже средней"
                item["load_class"] = "low"
            else:
                item["load_label"] = "Средняя"
                item["load_class"] = "normal"

    return sorted(
        merged.values(),
        key=lambda row: (-row.get("completed_count", 0), str(row.get("doctor_fio") or "")),
    )


def _decorate_statuses(raw: dict[str, Any]) -> dict[str, Any]:
    counts = {
        "completed": _number(raw.get("completed")),
        "planned": _number(raw.get("planned")),
        "no_show": _number(raw.get("no_show")),
        "cancelled": _number(raw.get("cancelled")),
    }
    total = _number(raw.get("total")) or sum(counts.values())
    result: dict[str, Any] = {**counts, "total": total}
    cumulative = 0.0
    for key in ("completed", "planned", "no_show", "cancelled"):
        value = _percent(counts[key], total)
        result[f"{key}_percent"] = value
        cumulative += value
        result[f"{key}_end"] = min(100.0, round(cumulative, 1))
    return result


def build_dashboard(filters: AnalyticsFilters) -> dict[str, Any]:
    options = get_analytics_filter_options()
    appointment_summary = get_appointment_summary(filters)
    schedule_summary = get_schedule_summary(filters)
    departments = _merge_departments(
        get_appointment_department_stats(filters),
        get_schedule_department_stats(filters),
    )
    doctors = _merge_doctors(
        get_appointment_doctor_stats(filters),
        get_schedule_doctor_stats(filters),
    )
    statuses = _decorate_statuses(get_schedule_statuses(filters))
    schedule_count = _number(schedule_summary.get("schedule_count"))
    no_show_count = _number(schedule_summary.get("no_show_count"))
    summary = {
        "schedule_count": schedule_count,
        "completed_count": _number(appointment_summary.get("completed_count")),
        "doctors_count": _number(appointment_summary.get("doctors_count")),
        "no_show_count": no_show_count,
        "no_show_rate": _percent(no_show_count, schedule_count),
    }
    return {
        "filters": filters,
        "filter_query": filters.as_query(),
        "locations": options["locations"],
        "doctors": options["doctors"],
        "summary": summary,
        "departments": departments,
        "doctors_stats": doctors,
        "statuses": statuses,
    }


def _metadata(filters: AnalyticsFilters, generated_by: str) -> list[tuple[str, Any]]:
    return [
        ("Период", f"{filters.date_from:%d.%m.%Y} — {filters.date_to:%d.%m.%Y}"),
        ("Сформировал", generated_by or "Пользователь МИС"),
        ("Дата формирования", datetime.now().strftime("%d.%m.%Y %H:%M")),
    ]


def _summary_sheet(dashboard: dict[str, Any], metadata: list[tuple[str, Any]]) -> XlsxSheet:
    summary = dashboard["summary"]
    return XlsxSheet(
        name="Сводка",
        title="Административная аналитика",
        metadata=metadata,
        headers=["Показатель", "Значение"],
        rows=[
            ["Записей в расписании", summary["schedule_count"]],
            ["Проведено приёмов", summary["completed_count"]],
            ["Врачей с приёмами", summary["doctors_count"]],
            ["Неявок", summary["no_show_count"]],
            ["Доля неявок, %", summary["no_show_rate"]],
        ],
        widths=[34, 18],
    )


def _doctors_sheet(dashboard: dict[str, Any], metadata: list[tuple[str, Any]]) -> XlsxSheet:
    return XlsxSheet(
        name="Врачи",
        title="Нагрузка по врачам",
        metadata=metadata,
        headers=[
            "Врач", "Отделение", "Проведено приёмов", "Рабочих дней",
            "Среднее приёмов в день", "Первичных", "Повторных", "Неявок",
            "Отмен", "Нагрузка",
        ],
        rows=[
            [
                row.get("doctor_fio"), row.get("location_display_name"),
                row.get("completed_count"), row.get("active_days"),
                row.get("average_per_day"), row.get("primary_count"),
                row.get("repeat_count"), row.get("no_show_count"),
                row.get("cancelled_count"), row.get("load_label"),
            ]
            for row in dashboard["doctors_stats"]
        ],
        widths=[30, 34, 18, 16, 22, 14, 14, 12, 12, 20],
    )


def _departments_sheet(dashboard: dict[str, Any], metadata: list[tuple[str, Any]]) -> XlsxSheet:
    return XlsxSheet(
        name="Отделения",
        title="Сводка по отделениям",
        metadata=metadata,
        headers=[
            "Отделение", "Врачей с приёмами", "Записей", "Проведено приёмов",
            "Первичных", "Повторных", "Неявок", "Отмен", "Доля неявок, %",
            "Среднее приёмов в день",
        ],
        rows=[
            [
                row.get("display_name"), row.get("doctors_count"),
                row.get("schedule_count"), row.get("completed_count"),
                row.get("primary_count"), row.get("repeat_count"),
                row.get("no_show_count"), row.get("cancelled_count"),
                row.get("no_show_rate"), row.get("average_per_day"),
            ]
            for row in dashboard["departments"]
        ],
        widths=[36, 20, 14, 20, 14, 14, 12, 12, 18, 23],
    )


def _statuses_sheet(dashboard: dict[str, Any], metadata: list[tuple[str, Any]]) -> XlsxSheet:
    statuses = dashboard["statuses"]
    labels = {
        "completed": "Проведено по записи",
        "planned": "Запланировано",
        "no_show": "Неявка",
        "cancelled": "Отменено",
    }
    return XlsxSheet(
        name="Статусы",
        title="Статусы записей в расписании",
        metadata=metadata,
        headers=["Статус", "Количество", "Доля, %"],
        rows=[
            [labels[key], statuses[key], statuses[f"{key}_percent"]]
            for key in ("completed", "planned", "no_show", "cancelled")
        ],
        widths=[32, 16, 14],
    )


def _issues_sheet(dashboard: dict[str, Any], metadata: list[tuple[str, Any]]) -> XlsxSheet:
    return XlsxSheet(
        name="Неявки и отмены",
        title="Неявки и отмены по врачам",
        metadata=metadata,
        headers=["Врач", "Отделение", "Записей", "Неявок", "Отмен", "Доля неявок, %"],
        rows=[
            [
                row.get("doctor_fio"), row.get("location_display_name"),
                row.get("schedule_count"), row.get("no_show_count"),
                row.get("cancelled_count"), row.get("no_show_rate"),
            ]
            for row in dashboard["doctors_stats"]
            if row.get("no_show_count") or row.get("cancelled_count")
        ],
        widths=[30, 34, 14, 12, 12, 18],
    )


def build_analytics_xlsx(
    filters: AnalyticsFilters,
    report: str,
    *,
    generated_by: str,
) -> tuple[bytes, str]:
    report = report if report in REPORT_LABELS else "all"
    dashboard = build_dashboard(filters)
    metadata = _metadata(filters, generated_by)
    builders = {
        "summary": _summary_sheet,
        "doctors": _doctors_sheet,
        "departments": _departments_sheet,
        "statuses": _statuses_sheet,
        "issues": _issues_sheet,
    }
    if report == "all":
        sheets = [
            builders["summary"](dashboard, metadata),
            builders["doctors"](dashboard, metadata),
            builders["departments"](dashboard, metadata),
            builders["statuses"](dashboard, metadata),
            builders["issues"](dashboard, metadata),
        ]
    else:
        sheets = [builders[report](dashboard, metadata)]
    filename = f"analytics_{report}_{filters.date_from.isoformat()}_{filters.date_to.isoformat()}.xlsx"
    return build_xlsx(sheets, title=REPORT_LABELS[report]), filename
