"""Динамические списки пациентов по клиническим показателям.

Модуль изолирован от остальных repositories: он читает существующие таблицы,
не меняет схему БД и возвращает только данные для страницы списков пациентов.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.parse import urlencode

from app.db.connection import get_db_connection


INDICATORS: dict[str, dict[str, Any]] = {
    "hemoglobin": {
        "label": "Гемоглобин",
        "unit": "г/л",
        "table": "cbc_results",
        "column": "hemoglobin",
        "date_sql": "r.investigation_date",
        "default_operator": "lt",
        "default_from": Decimal("120"),
        "default_to": None,
    },
    "potassium": {
        "label": "Калий",
        "unit": "ммоль/л",
        "table": "biochemistry_results",
        "column": "potassium",
        "date_sql": "r.investigation_date",
        "default_operator": "gt",
        "default_from": Decimal("5.5"),
        "default_to": None,
    },
    "ptg": {
        "label": "ПТГ",
        "unit": "пг/мл",
        "table": "biochemistry_results",
        "column": "ptg",
        "date_sql": "r.investigation_date",
        "default_operator": "gt",
        "default_from": Decimal("150"),
        "default_to": None,
    },
    "egfr": {
        "label": "СКФ CKD-EPI 2021",
        "unit": "мл/мин/1,73 м²",
        "table": "calculated_metrics",
        "column": "egfr_ckdepi",
        "date_sql": "COALESCE(r.investigation_date, a.appointment_date::date)",
        "default_operator": "lt",
        "default_from": Decimal("30"),
        "default_to": None,
    },
}

EGFR_CATEGORIES: dict[str, dict[str, Any]] = {
    "С1": {"label": "С1 — 90 и выше", "minimum": Decimal("90"), "maximum": None},
    "С2": {"label": "С2 — 60–89", "minimum": Decimal("60"), "maximum": Decimal("90")},
    "С3а": {"label": "С3а — 45–59", "minimum": Decimal("45"), "maximum": Decimal("60")},
    "С3б": {"label": "С3б — 30–44", "minimum": Decimal("30"), "maximum": Decimal("45")},
    "С4": {"label": "С4 — 15–29", "minimum": Decimal("15"), "maximum": Decimal("30")},
    "С5": {"label": "С5 — ниже 15", "minimum": None, "maximum": Decimal("15")},
}

PERIOD_LABELS = {
    0: "за всё время",
    1: "за последний месяц",
    3: "за последние 3 месяца",
    6: "за последние 6 месяцев",
    12: "за последний год",
}

OPERATOR_LABELS = {
    "lt": "ниже",
    "gt": "выше",
    "between": "от–до",
}


def _decimal(value: Any, default: Decimal | None = None) -> Decimal | None:
    if value in (None, ""):
        return default
    try:
        parsed = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _positive_int(value: Any, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, 1), maximum)


@dataclass(frozen=True)
class PatientListFilters:
    indicator: str = "hemoglobin"
    mode: str = "manual"
    operator: str = "lt"
    value_from: Decimal = Decimal("120")
    value_to: Decimal | None = None
    egfr_category: str = "С4"
    period_months: int = 6
    page: int = 1
    page_size: int = 25

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "PatientListFilters":
        indicator = str(values.get("indicator") or "hemoglobin")
        if indicator not in INDICATORS:
            indicator = "hemoglobin"
        spec = INDICATORS[indicator]

        mode = str(values.get("mode") or ("category" if indicator == "egfr" else "manual"))
        if indicator != "egfr" or mode not in {"category", "manual"}:
            mode = "manual"

        operator = str(values.get("operator") or spec["default_operator"])
        if operator not in OPERATOR_LABELS:
            operator = spec["default_operator"]

        value_from = _decimal(values.get("value_from"), spec["default_from"])
        if value_from is None:
            value_from = spec["default_from"]
        value_to = _decimal(values.get("value_to"), spec["default_to"])
        if operator == "between":
            if value_to is None:
                value_to = value_from
            if value_to < value_from:
                value_from, value_to = value_to, value_from
        else:
            value_to = None

        category = str(values.get("egfr_category") or "С4")
        if category not in EGFR_CATEGORIES:
            category = "С4"

        try:
            period_months = int(values.get("period_months", 6))
        except (TypeError, ValueError):
            period_months = 6
        if period_months not in PERIOD_LABELS:
            period_months = 6

        return cls(
            indicator=indicator,
            mode=mode,
            operator=operator,
            value_from=value_from,
            value_to=value_to,
            egfr_category=category,
            period_months=period_months,
            page=_positive_int(values.get("page"), 1, 100000),
            page_size=_positive_int(values.get("page_size"), 25, 100),
        )

    @property
    def indicator_spec(self) -> dict[str, Any]:
        return INDICATORS[self.indicator]

    def without_page_query(self) -> str:
        values = {
            "indicator": self.indicator,
            "mode": self.mode,
            "operator": self.operator,
            "value_from": _plain_number(self.value_from),
            "egfr_category": self.egfr_category,
            "period_months": self.period_months,
            "page_size": self.page_size,
        }
        if self.value_to is not None:
            values["value_to"] = _plain_number(self.value_to)
        return urlencode(values)


def _plain_number(value: Decimal | float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        text = format(value, "f")
    else:
        text = str(value)
    return text.rstrip("0").rstrip(".") if "." in text else text


def _category_sql(value_sql: str = "latest.result_value") -> str:
    return f"""
        CASE
            WHEN {value_sql} >= 90 THEN 'С1'
            WHEN {value_sql} >= 60 THEN 'С2'
            WHEN {value_sql} >= 45 THEN 'С3а'
            WHEN {value_sql} >= 30 THEN 'С3б'
            WHEN {value_sql} >= 15 THEN 'С4'
            ELSE 'С5'
        END
    """


def _condition_sql(filters: PatientListFilters) -> str:
    if filters.indicator == "egfr" and filters.mode == "category":
        category = EGFR_CATEGORIES[filters.egfr_category]
        minimum = category["minimum"]
        maximum = category["maximum"]
        if minimum is None:
            return "latest.result_value < %(category_max)s"
        if maximum is None:
            return "latest.result_value >= %(category_min)s"
        return "latest.result_value >= %(category_min)s AND latest.result_value < %(category_max)s"

    if filters.operator == "gt":
        return "latest.result_value > %(value_from)s"
    if filters.operator == "between":
        return "latest.result_value >= %(value_from)s AND latest.result_value <= %(value_to)s"
    return "latest.result_value < %(value_from)s"


def _patient_list_sql(filters: PatientListFilters) -> str:
    spec = filters.indicator_spec
    source_table = spec["table"]
    source_column = spec["column"]
    source_date = spec["date_sql"]
    condition = _condition_sql(filters)
    sort_direction = "DESC" if filters.operator == "gt" else "ASC"
    category_sql = _category_sql()

    # Названия таблиц и колонок берутся только из INDICATORS, пользовательские
    # значения передаются исключительно параметрами psycopg2.
    return f"""
        WITH observation AS (
            SELECT DISTINCT ON (a.patient_id)
                a.patient_id,
                a.id AS first_appointment_id,
                a.appointment_date AS first_appointment_date
            FROM appointments a
            ORDER BY a.patient_id, a.appointment_date ASC, a.id ASC
        ),
        latest_appointment AS (
            SELECT DISTINCT ON (a.patient_id)
                a.patient_id,
                a.id AS appointment_id,
                a.appointment_date,
                d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_name
            FROM appointments a
            JOIN doctors d ON d.id = a.doctor_id
            ORDER BY a.patient_id, a.appointment_date DESC, a.id DESC
        ),
        indicator_values AS (
            SELECT
                a.patient_id,
                a.id AS appointment_id,
                {source_date} AS result_date,
                r.{source_column}::numeric AS result_value
            FROM {source_table} r
            JOIN appointments a ON a.id = r.appointment_id
            WHERE r.{source_column} IS NOT NULL
        ),
        first_visit_value AS (
            SELECT
                obs.patient_id,
                iv.result_date,
                iv.result_value
            FROM observation obs
            LEFT JOIN LATERAL (
                SELECT result_date, result_value
                FROM indicator_values
                WHERE appointment_id = obs.first_appointment_id
                ORDER BY result_date ASC
                LIMIT 1
            ) iv ON TRUE
        ),
        latest_value AS (
            SELECT DISTINCT ON (patient_id)
                patient_id,
                appointment_id,
                result_date,
                result_value
            FROM indicator_values
            WHERE (
                %(period_months)s = 0
                OR result_date >= CURRENT_DATE - make_interval(months => %(period_months)s)
            )
            ORDER BY patient_id, result_date DESC, appointment_id DESC
        ),
        iron_prescriptions AS (
            SELECT
                a.patient_id,
                TRUE AS has_iron_prescription,
                STRING_AGG(DISTINCT pr.medication, ', ') AS iron_medications
            FROM prescriptions pr
            JOIN appointments a ON a.id = pr.appointment_id
            WHERE pr.medication IS NOT NULL
              AND pr.medication ILIKE ANY (ARRAY[
                    '%%желез%%', '%%феррум%%', '%%ferrum%%', '%%феринжект%%',
                    '%%венофер%%', '%%мальтофер%%', '%%сорбифер%%', '%%тардиферон%%'
              ])
            GROUP BY a.patient_id
        )
        SELECT
            COUNT(*) OVER() AS total_count,
            p.id AS patient_id,
            TRIM(p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '')) AS patient_fio,
            p.birth_date,
            EXTRACT(YEAR FROM AGE(last_visit.appointment_date, p.birth_date))::int AS age,
            CASE WHEN p.gender THEN 'М' ELSE 'Ж' END AS gender,
            obs.first_appointment_date,
            (CURRENT_DATE - obs.first_appointment_date::date) AS observation_days,
            first_visit.result_value AS first_visit_value,
            first_visit.result_date AS first_visit_value_date,
            latest.result_value AS latest_value,
            latest.result_date AS latest_value_date,
            ROUND((latest.result_value - first_visit.result_value)::numeric, 2) AS value_change,
            CASE WHEN %(indicator)s = 'egfr' THEN {category_sql} ELSE NULL END AS egfr_category,
            last_visit.appointment_date AS last_appointment_date,
            last_visit.doctor_name AS last_doctor_name,
            COALESCE(iron.has_iron_prescription, FALSE) AS has_iron_prescription,
            iron.iron_medications
        FROM patients p
        JOIN latest_value latest ON latest.patient_id = p.id
        LEFT JOIN first_visit_value first_visit ON first_visit.patient_id = p.id
        LEFT JOIN observation obs ON obs.patient_id = p.id
        LEFT JOIN latest_appointment last_visit ON last_visit.patient_id = p.id
        LEFT JOIN iron_prescriptions iron ON iron.patient_id = p.id
        WHERE {condition}
        ORDER BY latest.result_value {sort_direction}, p.last_name, p.first_name, p.id
        LIMIT %(limit)s OFFSET %(offset)s
    """


def _query_params(filters: PatientListFilters) -> dict[str, Any]:
    category = EGFR_CATEGORIES[filters.egfr_category]
    return {
        "indicator": filters.indicator,
        "period_months": filters.period_months,
        "value_from": filters.value_from,
        "value_to": filters.value_to,
        "category_min": category["minimum"],
        "category_max": category["maximum"],
        "limit": filters.page_size,
        "offset": (filters.page - 1) * filters.page_size,
    }


def _format_observation(days: Any) -> str:
    try:
        total_days = max(int(days), 0)
    except (TypeError, ValueError):
        return "—"
    years, remainder = divmod(total_days, 365)
    months = remainder // 30
    parts: list[str] = []
    if years:
        parts.append(f"{years} г.")
    if months:
        parts.append(f"{months} мес.")
    return " ".join(parts) if parts else "менее месяца"


def describe_filters(filters: PatientListFilters) -> str:
    spec = filters.indicator_spec
    period = PERIOD_LABELS[filters.period_months]
    if filters.indicator == "egfr" and filters.mode == "category":
        category = EGFR_CATEGORIES[filters.egfr_category]["label"]
        return f"Последняя {spec['label']} в категории {category} {period}"
    if filters.operator == "between":
        condition = f"от {_plain_number(filters.value_from)} до {_plain_number(filters.value_to)}"
    else:
        condition = f"{OPERATOR_LABELS[filters.operator]} {_plain_number(filters.value_from)}"
    return f"Последний показатель «{spec['label']}» {condition} {spec['unit']} {period}"


def get_patient_list(filters: PatientListFilters) -> dict[str, Any]:
    """Возвращает одну страницу динамического списка пациентов."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_patient_list_sql(filters), _query_params(filters))
            raw_rows = cur.fetchall()

    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        row = dict(raw)
        row["observation_duration"] = _format_observation(row.get("observation_days"))
        rows.append(row)

    total = int(rows[0]["total_count"]) if rows else 0
    pages = max((total + filters.page_size - 1) // filters.page_size, 1)
    return {
        "rows": rows,
        "total": total,
        "pages": pages,
        "page": filters.page,
        "page_size": filters.page_size,
        "description": describe_filters(filters),
        "query_without_page": filters.without_page_query(),
    }


def get_patient_indicator_history(patient_id: int, indicator: str) -> dict[str, Any] | None:
    """Возвращает все значения выбранного показателя за срок наблюдения пациента."""
    if indicator not in INDICATORS:
        raise ValueError("Неизвестный показатель")

    spec = INDICATORS[indicator]
    source_table = spec["table"]
    source_column = spec["column"]
    source_date = spec["date_sql"]
    history_sql = f"""
        SELECT
            {source_date} AS result_date,
            r.{source_column}::numeric AS result_value
        FROM {source_table} r
        JOIN appointments a ON a.id = r.appointment_id
        WHERE a.patient_id = %(patient_id)s
          AND r.{source_column} IS NOT NULL
          AND {source_date} IS NOT NULL
        ORDER BY result_date ASC, a.id ASC
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                    SELECT
                        p.id AS patient_id,
                        TRIM(p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '')) AS patient_fio,
                        p.birth_date
                    FROM patients p
                    WHERE p.id = %(patient_id)s
                """,
                {"patient_id": patient_id},
            )
            patient_raw = cur.fetchone()
            if patient_raw is None:
                return None
            cur.execute(history_sql, {"patient_id": patient_id})
            history_rows = cur.fetchall()
    patient = dict(patient_raw)
    patient.update(
        {
            "indicator": indicator,
            "indicator_label": spec["label"],
            "unit": spec["unit"],
            "points": [
                {"date": row["result_date"], "value": row["result_value"]}
                for row in map(dict, history_rows)
            ],
        }
    )
    return patient


def build_patient_list_csv(filters: PatientListFilters) -> tuple[str, str]:
    """Формирует CSV текущей выборки; структура БД при этом не меняется."""
    export_filters = replace(filters, page=1, page_size=10000)
    result = get_patient_list(export_filters)
    spec = filters.indicator_spec

    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Сформировано", datetime.now().strftime("%d.%m.%Y %H:%M")])
    writer.writerow(["Условие", _csv_text(result["description"])])
    writer.writerow([])
    headers = [
        "ФИО",
        "Дата рождения",
        "Пол",
        "Наблюдается",
        f"Значение на первом приёме, {spec['unit']}",
        "Дата первого приёма",
        f"Последнее значение, {spec['unit']}",
        "Дата последнего значения",
        "Изменение",
    ]
    if filters.indicator == "egfr":
        headers.append("Категория СКФ")
    if filters.indicator == "hemoglobin":
        headers.extend(["Назначения железа", "Найденные препараты"])
    headers.extend(["Последний приём", "Последний врач"])
    writer.writerow(headers)

    for row in result["rows"]:
        values = [
            _csv_text(row.get("patient_fio")),
            _format_date(row.get("birth_date")),
            row.get("gender") or "",
            row.get("observation_duration") or "",
            _csv_number(row.get("first_visit_value")),
            _format_date(row.get("first_appointment_date")),
            _csv_number(row.get("latest_value")),
            _format_date(row.get("latest_value_date")),
            _csv_number(row.get("value_change")),
        ]
        if filters.indicator == "egfr":
            values.append(row.get("egfr_category") or "")
        if filters.indicator == "hemoglobin":
            values.extend([
                "есть" if row.get("has_iron_prescription") else "нет",
                _csv_text(row.get("iron_medications")),
            ])
        values.extend([
            _format_date(row.get("last_appointment_date")),
            _csv_text(row.get("last_doctor_name")),
        ])
        writer.writerow(values)

    filename = f"patient_lists_{date.today().isoformat()}.csv"
    return "\ufeff" + output.getvalue(), filename


def _format_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _csv_number(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace(".", ",")


def _csv_text(value: Any) -> str:
    """Не позволяет табличному редактору выполнить формулу из текстового поля."""
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text
