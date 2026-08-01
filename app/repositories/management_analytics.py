"""SQL-запросы административной аналитики по приёмам и расписанию."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping
from urllib.parse import urlencode

from app.db.connection import get_db_connection


_EFFECTIVE_SCHEDULE_DOCTOR = """
CASE
    WHEN e.appointment_id IS NOT NULL
        THEN COALESCE(e.actual_doctor_id, e.scheduled_doctor_id)
    ELSE e.scheduled_doctor_id
END
"""


@dataclass(frozen=True)
class AnalyticsFilters:
    date_from: date
    date_to: date
    location_id: int | None = None
    doctor_id: int | None = None

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "AnalyticsFilters":
        today = date.today()
        default_from = today.replace(day=1)

        def parse_date(value: Any, default: date) -> date:
            try:
                return date.fromisoformat(str(value or ""))
            except ValueError:
                return default

        def positive_int(value: Any) -> int | None:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                return None
            return parsed if parsed > 0 else None

        date_from = parse_date(values.get("date_from"), default_from)
        date_to = parse_date(values.get("date_to"), today)
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        return cls(
            date_from=date_from,
            date_to=date_to,
            location_id=positive_int(
                values.get("analytics_location_id", values.get("location_id"))
            ),
            doctor_id=positive_int(
                values.get("analytics_doctor_id", values.get("doctor_id"))
            ),
        )

    def as_query(self) -> str:
        values: dict[str, Any] = {
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
        }
        if self.location_id:
            values["location_id"] = self.location_id
        if self.doctor_id:
            values["doctor_id"] = self.doctor_id
        return urlencode(values)


def _appointment_where(filters: AnalyticsFilters, alias: str = "r") -> tuple[str, list[Any]]:
    clauses = [
        f"{alias}.appointment_date >= %s::date",
        f"{alias}.appointment_date < (%s::date + INTERVAL '1 day')",
    ]
    params: list[Any] = [filters.date_from, filters.date_to]
    if filters.location_id:
        clauses.append(f"{alias}.location_id = %s")
        params.append(filters.location_id)
    if filters.doctor_id:
        clauses.append(f"{alias}.doctor_id = %s")
        params.append(filters.doctor_id)
    return " AND ".join(clauses), params


def _schedule_where(filters: AnalyticsFilters, alias: str = "e") -> tuple[str, list[Any]]:
    clauses = [
        f"{alias}.starts_at >= %s::date",
        f"{alias}.starts_at < (%s::date + INTERVAL '1 day')",
    ]
    params: list[Any] = [filters.date_from, filters.date_to]
    if filters.location_id:
        clauses.append(f"{alias}.location_id = %s")
        params.append(filters.location_id)
    if filters.doctor_id:
        effective = _EFFECTIVE_SCHEDULE_DOCTOR.replace("e.", f"{alias}.")
        clauses.append(f"({effective}) = %s")
        params.append(filters.doctor_id)
    return " AND ".join(clauses), params


def get_analytics_filter_options() -> dict[str, list[dict[str, Any]]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    l.id,
                    l.name,
                    b.name AS branch_name,
                    CASE
                        WHEN b.name IS NULL OR b.name = l.name THEN l.name
                        ELSE b.name || ' — ' || l.name
                    END AS display_name
                FROM locations l
                LEFT JOIN branches b ON b.id = l.branch_id
                ORDER BY b.name NULLS LAST, l.name, l.id
                """
            )
            locations = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT
                    d.id,
                    trim(concat_ws(' ', d.last_name, d.first_name, d.patronymic)) AS fio,
                    COALESCE(
                        array_agg(DISTINCT dl.location_id)
                            FILTER (WHERE dl.location_id IS NOT NULL),
                        ARRAY[]::integer[]
                    ) AS location_ids
                FROM doctors d
                LEFT JOIN doctor_locations dl ON dl.doctor_id = d.id
                GROUP BY d.id, d.last_name, d.first_name, d.patronymic
                ORDER BY d.last_name, d.first_name, d.patronymic NULLS LAST, d.id
                """
            )
            doctors = [dict(row) for row in cur.fetchall()]
    return {"locations": locations, "doctors": doctors}


def get_appointment_summary(filters: AnalyticsFilters) -> dict[str, Any]:
    where, params = _appointment_where(filters)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS completed_count,
                    COUNT(DISTINCT r.doctor_id) AS doctors_count
                FROM appointments r
                WHERE {where}
                """,
                params,
            )
            return dict(cur.fetchone() or {})


def get_schedule_summary(filters: AnalyticsFilters) -> dict[str, Any]:
    where, params = _schedule_where(filters)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS schedule_count,
                    COUNT(*) FILTER (WHERE e.status = 'no_show') AS no_show_count,
                    COUNT(*) FILTER (WHERE e.status = 'cancelled') AS cancelled_count
                FROM schedule_entries e
                WHERE {where}
                """,
                params,
            )
            return dict(cur.fetchone() or {})


def get_schedule_statuses(filters: AnalyticsFilters) -> dict[str, Any]:
    where, params = _schedule_where(filters)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE e.appointment_id IS NOT NULL) AS completed,
                    COUNT(*) FILTER (
                        WHERE e.appointment_id IS NULL
                          AND e.status IN ('booked', 'arrived')
                    ) AS planned,
                    COUNT(*) FILTER (
                        WHERE e.appointment_id IS NULL AND e.status = 'no_show'
                    ) AS no_show,
                    COUNT(*) FILTER (
                        WHERE e.appointment_id IS NULL AND e.status = 'cancelled'
                    ) AS cancelled,
                    COUNT(*) AS total
                FROM schedule_entries e
                WHERE {where}
                """,
                params,
            )
            return dict(cur.fetchone() or {})


def get_appointment_department_stats(filters: AnalyticsFilters) -> list[dict[str, Any]]:
    where, params = _appointment_where(filters, "r")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH ranked AS (
                    SELECT
                        a.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY a.patient_id
                            ORDER BY a.appointment_date, a.id
                        ) AS patient_visit_number
                    FROM appointments a
                ), filtered AS (
                    SELECT
                        r.*,
                        COALESCE(
                            se.appointment_type,
                            CASE WHEN r.patient_visit_number = 1 THEN 'primary' ELSE 'repeat' END
                        ) AS effective_type
                    FROM ranked r
                    LEFT JOIN schedule_entries se ON se.appointment_id = r.id
                    WHERE {where}
                )
                SELECT
                    f.location_id,
                    l.name AS location_name,
                    b.name AS branch_name,
                    CASE
                        WHEN b.name IS NULL OR b.name = l.name THEN l.name
                        ELSE b.name || ' — ' || l.name
                    END AS display_name,
                    COUNT(*) AS completed_count,
                    COUNT(DISTINCT f.doctor_id) AS doctors_count,
                    COUNT(DISTINCT f.appointment_date::date) AS active_days,
                    COUNT(*) FILTER (WHERE f.effective_type = 'primary') AS primary_count,
                    COUNT(*) FILTER (WHERE f.effective_type = 'repeat') AS repeat_count
                FROM filtered f
                JOIN locations l ON l.id = f.location_id
                LEFT JOIN branches b ON b.id = l.branch_id
                GROUP BY f.location_id, l.name, b.name
                ORDER BY completed_count DESC, display_name
                """,
                params,
            )
            return [dict(row) for row in cur.fetchall()]


def get_schedule_department_stats(filters: AnalyticsFilters) -> list[dict[str, Any]]:
    where, params = _schedule_where(filters)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    e.location_id,
                    l.name AS location_name,
                    b.name AS branch_name,
                    CASE
                        WHEN b.name IS NULL OR b.name = l.name THEN l.name
                        ELSE b.name || ' — ' || l.name
                    END AS display_name,
                    COUNT(*) AS schedule_count,
                    COUNT(*) FILTER (WHERE e.status = 'no_show') AS no_show_count,
                    COUNT(*) FILTER (WHERE e.status = 'cancelled') AS cancelled_count
                FROM schedule_entries e
                JOIN locations l ON l.id = e.location_id
                LEFT JOIN branches b ON b.id = l.branch_id
                WHERE {where}
                GROUP BY e.location_id, l.name, b.name
                """,
                params,
            )
            return [dict(row) for row in cur.fetchall()]


def get_appointment_doctor_stats(filters: AnalyticsFilters) -> list[dict[str, Any]]:
    where, params = _appointment_where(filters, "r")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH ranked AS (
                    SELECT
                        a.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY a.patient_id
                            ORDER BY a.appointment_date, a.id
                        ) AS patient_visit_number
                    FROM appointments a
                ), filtered AS (
                    SELECT
                        r.*,
                        COALESCE(
                            se.appointment_type,
                            CASE WHEN r.patient_visit_number = 1 THEN 'primary' ELSE 'repeat' END
                        ) AS effective_type
                    FROM ranked r
                    LEFT JOIN schedule_entries se ON se.appointment_id = r.id
                    WHERE {where}
                )
                SELECT
                    f.doctor_id,
                    f.location_id,
                    trim(concat_ws(' ', d.last_name, d.first_name, d.patronymic)) AS doctor_fio,
                    l.name AS location_name,
                    b.name AS branch_name,
                    CASE
                        WHEN b.name IS NULL OR b.name = l.name THEN l.name
                        ELSE b.name || ' — ' || l.name
                    END AS location_display_name,
                    COUNT(*) AS completed_count,
                    COUNT(DISTINCT f.appointment_date::date) AS active_days,
                    COUNT(*) FILTER (WHERE f.effective_type = 'primary') AS primary_count,
                    COUNT(*) FILTER (WHERE f.effective_type = 'repeat') AS repeat_count
                FROM filtered f
                JOIN doctors d ON d.id = f.doctor_id
                JOIN locations l ON l.id = f.location_id
                LEFT JOIN branches b ON b.id = l.branch_id
                GROUP BY
                    f.doctor_id, f.location_id,
                    d.last_name, d.first_name, d.patronymic,
                    l.name, b.name
                ORDER BY completed_count DESC, doctor_fio, location_display_name
                """,
                params,
            )
            return [dict(row) for row in cur.fetchall()]


def get_schedule_doctor_stats(filters: AnalyticsFilters) -> list[dict[str, Any]]:
    where, params = _schedule_where(filters)
    effective = _EFFECTIVE_SCHEDULE_DOCTOR
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH filtered AS (
                    SELECT
                        e.*,
                        {effective} AS effective_doctor_id
                    FROM schedule_entries e
                    WHERE {where}
                )
                SELECT
                    f.effective_doctor_id AS doctor_id,
                    f.location_id,
                    trim(concat_ws(' ', d.last_name, d.first_name, d.patronymic)) AS doctor_fio,
                    l.name AS location_name,
                    b.name AS branch_name,
                    CASE
                        WHEN b.name IS NULL OR b.name = l.name THEN l.name
                        ELSE b.name || ' — ' || l.name
                    END AS location_display_name,
                    COUNT(*) AS schedule_count,
                    COUNT(*) FILTER (WHERE f.status = 'no_show') AS no_show_count,
                    COUNT(*) FILTER (WHERE f.status = 'cancelled') AS cancelled_count
                FROM filtered f
                JOIN doctors d ON d.id = f.effective_doctor_id
                JOIN locations l ON l.id = f.location_id
                LEFT JOIN branches b ON b.id = l.branch_id
                GROUP BY
                    f.effective_doctor_id, f.location_id,
                    d.last_name, d.first_name, d.patronymic,
                    l.name, b.name
                ORDER BY doctor_fio, location_display_name
                """,
                params,
            )
            return [dict(row) for row in cur.fetchall()]
