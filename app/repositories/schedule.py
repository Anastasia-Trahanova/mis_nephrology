"""
Repository модуля расписания.

Этот файл содержит только SQL для расписания:
- получение врачей и отделений для фильтров;
- создание слотов расписания;
- чтение сетки расписания;
- запись пациента на свободный слот;
- отмена записи;
- отметка "пришёл" / "не пришёл".

Не хранит HTML-логику и не создаёт медицинский приём в appointments.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import HTTPException

from app.db.connection import get_db_connection


SLOT_KIND_LABELS = {
    "primary": "Первичный",
    "repeat": "Повторный",
}

SLOT_STATUS_LABELS = {
    "free": "Свободно",
    "booked": "Записан",
    "blocked": "Недоступно",
    "cancelled": "Отменено",
    "completed": "Пришёл",
    "no_show": "Не пришёл",
}


# ---------------------------------------------------------------------------
# Справочники для страницы расписания
# ---------------------------------------------------------------------------


def get_schedule_doctors() -> list[dict[str, Any]]:
    """Возвращает всех врачей для фильтра расписания."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    last_name,
                    first_name,
                    patronymic,
                    last_name || ' ' || first_name || ' ' || COALESCE(patronymic, '') AS fio
                FROM doctors
                ORDER BY last_name, first_name, patronymic NULLS LAST
                """
            )
            return cur.fetchall()


def get_schedule_locations_for_doctor(doctor_id: int | None = None) -> list[dict[str, Any]]:
    """Возвращает отделения: все или только привязанные к врачу."""
    query = """
        SELECT DISTINCT
            l.id,
            l.name,
            b.name AS branch_name,
            l.name || ' — ' || b.name AS full_name
        FROM locations l
        JOIN branches b ON b.id = l.branch_id
    """
    params: list[Any] = []

    if doctor_id:
        query += " JOIN doctor_locations dl ON dl.location_id = l.id WHERE dl.doctor_id = %s"
        params.append(doctor_id)

    query += " ORDER BY b.name, l.name"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


# ---------------------------------------------------------------------------
# Слоты расписания
# ---------------------------------------------------------------------------


def generate_schedule_slots(
    *,
    doctor_id: int,
    location_id: int,
    date_from: date,
    date_to: date,
    weekdays: set[int],
    time_from: time,
    time_to: time,
    slot_minutes: int,
    slot_kind: str,
    note: str | None,
    created_by_user_id: int | None,
) -> int:
    """
    Создаёт слоты расписания по диапазону дат и времени.

    weekdays использует формат Python date.weekday():
    0 = понедельник, 6 = воскресенье.
    Уже существующие слоты не дублируются.
    """
    if date_to < date_from:
        raise HTTPException(status_code=400, detail="Дата окончания раньше даты начала")

    if slot_minutes <= 0 or slot_minutes > 240:
        raise HTTPException(status_code=400, detail="Некорректная длительность слота")

    if slot_kind not in SLOT_KIND_LABELS:
        raise HTTPException(status_code=400, detail="Некорректный тип приёма")

    if not weekdays:
        raise HTTPException(status_code=400, detail="Выберите хотя бы один день недели")

    inserted = 0
    step = timedelta(minutes=slot_minutes)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            day = date_from
            while day <= date_to:
                if day.weekday() in weekdays:
                    start_dt = datetime.combine(day, time_from)
                    end_limit = datetime.combine(day, time_to)

                    while start_dt + step <= end_limit:
                        end_dt = start_dt + step
                        cur.execute(
                            """
                            INSERT INTO schedule_slots (
                                doctor_id,
                                location_id,
                                starts_at,
                                ends_at,
                                slot_kind,
                                status,
                                note,
                                created_by_user_id
                            )
                            VALUES (%s, %s, %s, %s, %s, 'free', %s, %s)
                            ON CONFLICT (doctor_id, starts_at, ends_at) DO NOTHING
                            RETURNING id
                            """,
                            (
                                doctor_id,
                                location_id,
                                start_dt,
                                end_dt,
                                slot_kind,
                                note,
                                created_by_user_id,
                            ),
                        )
                        if cur.fetchone():
                            inserted += 1
                        start_dt = end_dt
                day += timedelta(days=1)

    return inserted


def get_schedule_slots(
    *,
    doctor_id: int,
    date_from: date,
    date_to: date,
    location_id: int | None = None,
) -> list[dict[str, Any]]:
    """Возвращает слоты врача за период вместе с активной записью пациента."""
    query = """
        SELECT
            s.id,
            s.doctor_id,
            s.location_id,
            s.starts_at,
            s.ends_at,
            s.slot_kind,
            s.status AS slot_status,
            s.note AS slot_note,
            d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_fio,
            l.name AS location_name,
            b.name AS branch_name,
            sb.id AS booking_id,
            sb.status AS booking_status,
            sb.reason AS booking_reason,
            sb.comment AS booking_comment,
            p.id AS patient_id,
            p.last_name,
            p.first_name,
            p.patronymic,
            p.birth_date,
            p.gender,
            p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio
        FROM schedule_slots s
        JOIN doctors d ON d.id = s.doctor_id
        JOIN locations l ON l.id = s.location_id
        JOIN branches b ON b.id = l.branch_id
        LEFT JOIN LATERAL (
            SELECT *
            FROM schedule_bookings sb0
            WHERE sb0.slot_id = s.id
              AND sb0.status IN ('booked', 'completed', 'no_show')
            ORDER BY sb0.id DESC
            LIMIT 1
        ) sb ON TRUE
        LEFT JOIN patients p ON p.id = sb.patient_id
        WHERE s.doctor_id = %s
          AND s.starts_at >= %s::date
          AND s.starts_at < (%s::date + INTERVAL '1 day')
    """
    params: list[Any] = [doctor_id, date_from, date_to]

    if location_id:
        query += " AND s.location_id = %s"
        params.append(location_id)

    query += " ORDER BY s.starts_at, s.ends_at"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    for row in rows:
        status = row.get("booking_status") or row.get("slot_status")
        row["status"] = status
        row["status_label"] = SLOT_STATUS_LABELS.get(status, status)
        row["slot_kind_label"] = SLOT_KIND_LABELS.get(row.get("slot_kind"), row.get("slot_kind"))
        row["date_iso"] = row["starts_at"].date().isoformat()
        row["time_label"] = f"{row['starts_at']:%H:%M}–{row['ends_at']:%H:%M}"
    return rows


# ---------------------------------------------------------------------------
# Запись пациента
# ---------------------------------------------------------------------------


def _find_patient_by_identity(
    cur: Any,
    *,
    last_name: str,
    first_name: str,
    patronymic: str | None,
    birth_date: date,
    gender: bool,
) -> int | None:
    """Ищет пациента по точному совпадению ФИО, даты рождения и пола."""
    cur.execute(
        """
        SELECT id
        FROM patients
        WHERE lower(last_name) = lower(%s)
          AND lower(first_name) = lower(%s)
          AND COALESCE(lower(patronymic), '') = COALESCE(lower(%s), '')
          AND birth_date = %s
          AND gender = %s
        ORDER BY id
        LIMIT 1
        """,
        (last_name, first_name, patronymic, birth_date, gender),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def _create_patient_for_booking(
    cur: Any,
    *,
    last_name: str,
    first_name: str,
    patronymic: str | None,
    birth_date: date,
    gender: bool,
) -> int:
    """Создаёт пациента для записи в расписании."""
    cur.execute(
        """
        INSERT INTO patients (last_name, first_name, patronymic, birth_date, gender)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (last_name, first_name, patronymic, birth_date, gender),
    )
    return cur.fetchone()["id"]


def book_schedule_slot(
    *,
    slot_id: int,
    last_name: str,
    first_name: str,
    patronymic: str | None,
    birth_date: date,
    gender: bool,
    reason: str | None,
    comment: str | None,
    booked_by_user_id: int | None,
) -> int:
    """Записывает пациента на свободный слот и возвращает booking_id."""
    last_name = last_name.strip()
    first_name = first_name.strip()
    patronymic = patronymic.strip() if patronymic else None

    if not last_name or not first_name:
        raise HTTPException(status_code=400, detail="Заполните фамилию и имя пациента")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status
                FROM schedule_slots
                WHERE id = %s
                FOR UPDATE
                """,
                (slot_id,),
            )
            slot = cur.fetchone()
            if not slot:
                raise HTTPException(status_code=404, detail="Слот расписания не найден")
            if slot["status"] != "free":
                raise HTTPException(status_code=400, detail="Этот слот уже недоступен для записи")

            cur.execute(
                """
                SELECT id
                FROM schedule_bookings
                WHERE slot_id = %s
                  AND status IN ('booked', 'completed', 'no_show')
                LIMIT 1
                """,
                (slot_id,),
            )
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="На этот слот уже есть активная запись")

            patient_id = _find_patient_by_identity(
                cur,
                last_name=last_name,
                first_name=first_name,
                patronymic=patronymic,
                birth_date=birth_date,
                gender=gender,
            )
            if patient_id is None:
                patient_id = _create_patient_for_booking(
                    cur,
                    last_name=last_name,
                    first_name=first_name,
                    patronymic=patronymic,
                    birth_date=birth_date,
                    gender=gender,
                )

            cur.execute(
                """
                INSERT INTO schedule_bookings (
                    slot_id,
                    patient_id,
                    status,
                    reason,
                    comment,
                    booked_by_user_id
                )
                VALUES (%s, %s, 'booked', %s, %s, %s)
                RETURNING id
                """,
                (slot_id, patient_id, reason, comment, booked_by_user_id),
            )
            booking_id = cur.fetchone()["id"]

            cur.execute(
                """
                UPDATE schedule_slots
                SET status = 'booked', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (slot_id,),
            )

    return booking_id


def cancel_schedule_booking(
    *,
    booking_id: int,
    cancelled_by_user_id: int | None,
    cancel_reason: str | None = None,
) -> None:
    """Отменяет запись и снова освобождает слот."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, slot_id, status
                FROM schedule_bookings
                WHERE id = %s
                FOR UPDATE
                """,
                (booking_id,),
            )
            booking = cur.fetchone()
            if not booking:
                raise HTTPException(status_code=404, detail="Запись не найдена")
            if booking["status"] == "cancelled":
                return

            cur.execute(
                """
                UPDATE schedule_bookings
                SET
                    status = 'cancelled',
                    cancelled_by_user_id = %s,
                    cancelled_at = CURRENT_TIMESTAMP,
                    cancel_reason = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (cancelled_by_user_id, cancel_reason, booking_id),
            )

            cur.execute(
                """
                UPDATE schedule_slots
                SET status = 'free', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (booking["slot_id"],),
            )


def set_schedule_booking_status(
    *,
    booking_id: int,
    status: str,
) -> None:
    """Ставит отметку по прошедшей записи: пришёл / не пришёл."""
    if status not in {"completed", "no_show"}:
        raise HTTPException(status_code=400, detail="Некорректный статус записи")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, slot_id
                FROM schedule_bookings
                WHERE id = %s
                  AND status IN ('booked', 'completed', 'no_show')
                FOR UPDATE
                """,
                (booking_id,),
            )
            booking = cur.fetchone()
            if not booking:
                raise HTTPException(status_code=404, detail="Активная запись не найдена")

            cur.execute(
                """
                UPDATE schedule_bookings
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (status, booking_id),
            )
            cur.execute(
                """
                UPDATE schedule_slots
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (status, booking["slot_id"]),
            )
