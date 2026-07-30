"""SQL и транзакционная логика нового расписания."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import HTTPException

from app.db.connection import get_db_connection

APPOINTMENT_TYPE_LABELS = {"primary": "Первичный", "repeat": "Повторный"}
WALK_IN_NOTE = "Приём без записи"
WALK_IN_DURATION_MINUTES = 30
STATUS_LABELS = {
    "booked": "Ожидается",
    "arrived": "Пришёл",
    "no_show": "Не пришёл",
    "cancelled": "Отменён",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip(" ,")


def format_schedule_location(row: dict[str, Any]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for value in (
        row.get("company_name"),
        row.get("branch_name"),
        row.get("location_name"),
        row.get("factual_address"),
    ):
        part = _clean(value)
        key = part.casefold()
        if part and key not in seen:
            parts.append(part)
            seen.add(key)
    return ", ".join(parts)


def get_schedule_doctors() -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, last_name, first_name, patronymic,
                       trim(concat_ws(' ', last_name, first_name, patronymic)) AS fio
                FROM doctors
                ORDER BY last_name, first_name, patronymic NULLS LAST, id
                """
            )
            return [dict(row) for row in cur.fetchall()]


def _location_select_sql() -> str:
    return """
        SELECT DISTINCT
            l.id,
            l.name AS location_name,
            l.factual_address,
            b.name AS branch_name,
            c.name AS company_name
        FROM locations l
        LEFT JOIN branches b ON b.id = l.branch_id
        LEFT JOIN companies c ON c.id = COALESCE(l.company_id, b.company_id)
    """


def _decorate_locations(rows: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source in rows:
        item = dict(source)
        item["name"] = item.get("location_name")
        item["full_name"] = format_schedule_location(item)
        result.append(item)
    return result


def get_schedule_locations_for_doctor(doctor_id: int) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                _location_select_sql()
                + """
                JOIN doctor_locations dl ON dl.location_id = l.id
                WHERE dl.doctor_id = %s
                ORDER BY c.name NULLS LAST, b.name NULLS LAST,
                         l.name, l.factual_address NULLS LAST, l.id
                """,
                (doctor_id,),
            )
            return _decorate_locations(list(cur.fetchall()))


def get_schedule_location_by_id(location_id: int) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_location_select_sql() + " WHERE l.id = %s", (location_id,))
            row = cur.fetchone()
    return _decorate_locations([row])[0] if row else None


def _serialize_entry(row: Any) -> dict[str, Any]:
    item = dict(row)
    starts_at: datetime = item["starts_at"]
    ends_at: datetime = item["ends_at"]
    is_walk_in = _clean(item.get("note")).casefold() == WALK_IN_NOTE.casefold()
    appointment_type_label = APPOINTMENT_TYPE_LABELS.get(
        item.get("appointment_type"), item.get("appointment_type")
    )
    if is_walk_in and appointment_type_label:
        appointment_type_label = f"{appointment_type_label} приём\n{WALK_IN_NOTE}"
    item.update(
        {
            "starts_at": starts_at.isoformat(timespec="minutes"),
            "ends_at": ends_at.isoformat(timespec="minutes"),
            "date_iso": starts_at.date().isoformat(),
            "start_time": starts_at.strftime("%H:%M"),
            "end_time": ends_at.strftime("%H:%M"),
            "time_label": f"{starts_at:%H:%M}–{ends_at:%H:%M}",
            "appointment_type_label": appointment_type_label,
            "status_label": STATUS_LABELS.get(item.get("status"), item.get("status")),
            "location_full_name": format_schedule_location(item),
            "birth_date": item["birth_date"].isoformat() if item.get("birth_date") else None,
            "gender_value": "male" if item.get("gender") else "female",
            "is_walk_in": is_walk_in,
        }
    )
    return item


def get_schedule_entries(*, doctor_id: int, date_from: date, date_to: date) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    e.id, e.scheduled_doctor_id, e.location_id, e.patient_id,
                    e.starts_at, e.ends_at, e.appointment_type, e.status,
                    e.actual_doctor_id, e.appointment_id, e.note,
                    p.last_name, p.first_name, p.patronymic, p.birth_date,
                    p.phone, p.gender,
                    trim(concat_ws(' ', p.last_name, p.first_name, p.patronymic)) AS patient_fio,
                    trim(concat_ws(' ', d.last_name, d.first_name, d.patronymic)) AS scheduled_doctor_fio,
                    trim(concat_ws(' ', ad.last_name, ad.first_name, ad.patronymic)) AS actual_doctor_fio,
                    l.name AS location_name, l.factual_address,
                    b.name AS branch_name, c.name AS company_name
                FROM schedule_entries e
                JOIN patients p ON p.id = e.patient_id
                JOIN doctors d ON d.id = e.scheduled_doctor_id
                LEFT JOIN doctors ad ON ad.id = e.actual_doctor_id
                JOIN locations l ON l.id = e.location_id
                LEFT JOIN branches b ON b.id = l.branch_id
                LEFT JOIN companies c ON c.id = COALESCE(l.company_id, b.company_id)
                WHERE e.scheduled_doctor_id = %s
                  AND e.starts_at >= %s::date
                  AND e.starts_at < (%s::date + INTERVAL '1 day')
                ORDER BY e.starts_at, e.ends_at, e.id
                """,
                (doctor_id, date_from, date_to),
            )
            return [_serialize_entry(row) for row in cur.fetchall()]


def search_schedule_patients(
    *, last_name: str = "", first_name: str = "", patronymic: str = "", limit: int = 12
) -> list[dict[str, Any]]:
    last_name = _clean(last_name)
    first_name = _clean(first_name)
    patronymic = _clean(patronymic)
    if max(len(last_name), len(first_name), len(patronymic)) < 2:
        return []

    clauses: list[str] = []
    params: list[Any] = []
    for column, value in (
        ("p.last_name", last_name),
        ("p.first_name", first_name),
        ("COALESCE(p.patronymic, '')", patronymic),
    ):
        if value:
            clauses.append(f"{column} ILIKE %s")
            params.append(f"{value}%")
    params.append(max(1, min(limit, 30)))

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    p.id, p.last_name, p.first_name, p.patronymic,
                    p.birth_date, p.phone, p.gender,
                    trim(concat_ws(' ', p.last_name, p.first_name, p.patronymic)) AS fio,
                    EXISTS(SELECT 1 FROM appointments a WHERE a.patient_id = p.id) AS has_appointments
                FROM patients p
                WHERE {' AND '.join(clauses)}
                ORDER BY p.last_name, p.first_name, p.patronymic NULLS LAST, p.birth_date
                LIMIT %s
                """,
                params,
            )
            rows = []
            for row in cur.fetchall():
                item = dict(row)
                item["birth_date"] = item["birth_date"].isoformat() if item.get("birth_date") else None
                item["gender_value"] = "male" if item.get("gender") else "female"
                item["appointment_type"] = "repeat" if item.get("has_appointments") else "primary"
                item["appointment_type_label"] = APPOINTMENT_TYPE_LABELS[item["appointment_type"]]
                rows.append(item)
            return rows


def _doctor_location_allowed(cur: Any, doctor_id: int, location_id: int) -> bool:
    cur.execute(
        """
        SELECT 1 FROM doctor_locations
        WHERE doctor_id = %s AND location_id = %s
        LIMIT 1
        """,
        (doctor_id, location_id),
    )
    return cur.fetchone() is not None


def _lock_doctor_day(cur: Any, doctor_id: int, day: date) -> None:
    cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (doctor_id, day.toordinal()))


def _find_overlap(
    cur: Any,
    *,
    doctor_id: int,
    starts_at: datetime,
    ends_at: datetime,
    exclude_entry_id: int | None = None,
) -> dict[str, Any] | None:
    query = """
        SELECT id, starts_at, ends_at
        FROM schedule_entries
        WHERE scheduled_doctor_id = %s
          AND status <> 'cancelled'
          AND starts_at < %s
          AND ends_at > %s
    """
    params: list[Any] = [doctor_id, ends_at, starts_at]
    if exclude_entry_id is not None:
        query += " AND id <> %s"
        params.append(exclude_entry_id)
    query += " ORDER BY starts_at LIMIT 1 FOR UPDATE"
    cur.execute(query, params)
    row = cur.fetchone()
    return dict(row) if row else None


def _overlap_error(row: dict[str, Any]) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail=f"У врача уже есть запись с {row['starts_at']:%H:%M} до {row['ends_at']:%H:%M}",
    )


def _exact_patient(
    cur: Any,
    *,
    last_name: str,
    first_name: str,
    patronymic: str | None,
    birth_date: date,
    exclude_patient_id: int | None = None,
):
    query = """
        SELECT id, last_name, first_name, patronymic, birth_date, phone
        FROM patients
        WHERE lower(trim(last_name)) = lower(trim(%s))
          AND lower(trim(first_name)) = lower(trim(%s))
          AND lower(trim(COALESCE(patronymic, ''))) = lower(trim(COALESCE(%s, '')))
          AND birth_date = %s
    """
    params: list[Any] = [last_name, first_name, patronymic, birth_date]
    if exclude_patient_id is not None:
        query += " AND id <> %s"
        params.append(exclude_patient_id)
    query += " ORDER BY id LIMIT 1"
    cur.execute(query, params)
    return cur.fetchone()


def _validated_patient_data(
    *,
    last_name: str | None,
    first_name: str | None,
    patronymic: str | None,
    birth_date: date | None,
    phone: str | None,
    gender: bool | None,
) -> dict[str, Any]:
    data = {
        "last_name": _clean(last_name),
        "first_name": _clean(first_name),
        "patronymic": _clean(patronymic) or None,
        "birth_date": birth_date,
        "phone": _clean(phone),
        "gender": gender,
    }
    if (
        not data["last_name"]
        or not data["first_name"]
        or not data["birth_date"]
        or data["gender"] is None
        or not data["phone"]
    ):
        raise HTTPException(
            status_code=400,
            detail="Для нового пациента заполните ФИО, дату рождения, пол и телефон",
        )
    if data["birth_date"] > date.today():
        raise HTTPException(status_code=400, detail="Дата рождения не может быть в будущем")
    return data


def _patient_has_appointments(cur: Any, patient_id: int) -> bool:
    cur.execute(
        "SELECT EXISTS(SELECT 1 FROM appointments WHERE patient_id = %s) AS value",
        (patient_id,),
    )
    return bool(cur.fetchone()["value"])


def _create_patient_from_schedule(cur: Any, data: dict[str, Any]) -> int:
    duplicate = _exact_patient(
        cur,
        last_name=data["last_name"],
        first_name=data["first_name"],
        patronymic=data["patronymic"],
        birth_date=data["birth_date"],
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="Такой пациент уже есть в базе. Выберите его из подсказки поиска.",
        )
    cur.execute(
        """
        INSERT INTO patients(last_name, first_name, patronymic, birth_date, gender, phone)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            data["last_name"],
            data["first_name"],
            data["patronymic"],
            data["birth_date"],
            data["gender"],
            data["phone"],
        ),
    )
    return int(cur.fetchone()["id"])


def create_schedule_entry(
    *,
    scheduled_doctor_id: int,
    location_id: int,
    starts_at: datetime,
    ends_at: datetime,
    patient_id: int | None,
    last_name: str | None,
    first_name: str | None,
    patronymic: str | None,
    birth_date: date | None,
    phone: str | None,
    gender: bool | None,
    created_by_user_id: int | None,
) -> dict[str, Any]:
    if ends_at <= starts_at or starts_at.date() != ends_at.date():
        raise HTTPException(status_code=400, detail="Время окончания должно быть позже времени начала в тот же день")
    if starts_at.date() < date.today():
        raise HTTPException(status_code=400, detail="Нельзя создать запись на прошедшую дату")

    with get_db_connection() as conn:
        try:
            with conn.cursor() as cur:
                if not _doctor_location_allowed(cur, scheduled_doctor_id, location_id):
                    raise HTTPException(status_code=400, detail="Выбранное место не привязано к врачу")

                if patient_id:
                    cur.execute(
                        "SELECT id FROM patients WHERE id = %s FOR SHARE",
                        (patient_id,),
                    )
                    if not cur.fetchone():
                        raise HTTPException(status_code=404, detail="Пациент не найден")
                else:
                    patient_data = _validated_patient_data(
                        last_name=last_name,
                        first_name=first_name,
                        patronymic=patronymic,
                        birth_date=birth_date,
                        phone=phone,
                        gender=gender,
                    )
                    patient_id = _create_patient_from_schedule(cur, patient_data)

                appointment_type = "repeat" if _patient_has_appointments(cur, patient_id) else "primary"

                _lock_doctor_day(cur, scheduled_doctor_id, starts_at.date())
                overlap = _find_overlap(
                    cur,
                    doctor_id=scheduled_doctor_id,
                    starts_at=starts_at,
                    ends_at=ends_at,
                )
                if overlap:
                    raise _overlap_error(overlap)

                cur.execute(
                    """
                    INSERT INTO schedule_entries(
                        scheduled_doctor_id, location_id, patient_id,
                        starts_at, ends_at, appointment_type, status,
                        created_by_user_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'booked', %s)
                    RETURNING id
                    """,
                    (
                        scheduled_doctor_id,
                        location_id,
                        patient_id,
                        starts_at,
                        ends_at,
                        appointment_type,
                        created_by_user_id,
                    ),
                )
                entry_id = int(cur.fetchone()["id"])
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Не удалось сохранить запись: {exc}") from exc

    return get_schedule_entry(entry_id)


def get_schedule_entry(entry_id: int) -> dict[str, Any]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    e.id, e.scheduled_doctor_id, e.location_id, e.patient_id,
                    e.starts_at, e.ends_at, e.appointment_type, e.status,
                    e.actual_doctor_id, e.appointment_id, e.note,
                    p.last_name, p.first_name, p.patronymic, p.birth_date,
                    p.phone, p.gender,
                    trim(concat_ws(' ', p.last_name, p.first_name, p.patronymic)) AS patient_fio,
                    trim(concat_ws(' ', d.last_name, d.first_name, d.patronymic)) AS scheduled_doctor_fio,
                    trim(concat_ws(' ', ad.last_name, ad.first_name, ad.patronymic)) AS actual_doctor_fio,
                    l.name AS location_name, l.factual_address,
                    b.name AS branch_name, c.name AS company_name
                FROM schedule_entries e
                JOIN patients p ON p.id = e.patient_id
                JOIN doctors d ON d.id = e.scheduled_doctor_id
                LEFT JOIN doctors ad ON ad.id = e.actual_doctor_id
                JOIN locations l ON l.id = e.location_id
                LEFT JOIN branches b ON b.id = l.branch_id
                LEFT JOIN companies c ON c.id = COALESCE(l.company_id, b.company_id)
                WHERE e.id = %s
                """,
                (entry_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Запись расписания не найдена")
    return _serialize_entry(row)


def update_schedule_entry(
    *,
    entry_id: int,
    scheduled_doctor_id: int,
    location_id: int,
    starts_at: datetime,
    ends_at: datetime,
    patient_id: int | None,
    patient_mode: str,
    last_name: str | None,
    first_name: str | None,
    patronymic: str | None,
    birth_date: date | None,
    phone: str | None,
    gender: bool | None,
) -> dict[str, Any]:
    if ends_at <= starts_at or starts_at.date() != ends_at.date():
        raise HTTPException(
            status_code=400,
            detail="Время окончания должно быть позже времени начала в тот же день",
        )
    if starts_at.date() < date.today():
        raise HTTPException(status_code=400, detail="Нельзя перенести запись на прошедшую дату")
    if patient_mode not in {"selected", "edit_current", "new"}:
        raise HTTPException(status_code=400, detail="Некорректный режим выбора пациента")

    with get_db_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, patient_id, appointment_id, status
                    FROM schedule_entries
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (entry_id,),
                )
                current = cur.fetchone()
                if not current:
                    raise HTTPException(status_code=404, detail="Запись не найдена")
                if current["appointment_id"]:
                    raise HTTPException(
                        status_code=409,
                        detail="Нельзя изменять запись после сохранения медицинского приёма",
                    )
                if current["status"] == "cancelled":
                    raise HTTPException(status_code=409, detail="Отменённую запись нельзя редактировать")
                if not _doctor_location_allowed(cur, scheduled_doctor_id, location_id):
                    raise HTTPException(status_code=400, detail="Выбранное место не привязано к врачу")

                current_patient_id = int(current["patient_id"])
                target_patient_id: int
                if patient_mode == "selected":
                    if not patient_id:
                        raise HTTPException(status_code=400, detail="Выберите пациента из результатов поиска")
                    cur.execute("SELECT id FROM patients WHERE id = %s FOR SHARE", (patient_id,))
                    if not cur.fetchone():
                        raise HTTPException(status_code=404, detail="Пациент не найден")
                    target_patient_id = int(patient_id)
                elif patient_mode == "edit_current":
                    if not patient_id or int(patient_id) != current_patient_id:
                        raise HTTPException(status_code=400, detail="Нельзя изменить другого пациента")
                    if _patient_has_appointments(cur, current_patient_id):
                        raise HTTPException(
                            status_code=409,
                            detail="Данные пациента с сохранёнными приёмами изменяются только в карточке пациента",
                        )
                    patient_data = _validated_patient_data(
                        last_name=last_name,
                        first_name=first_name,
                        patronymic=patronymic,
                        birth_date=birth_date,
                        phone=phone,
                        gender=gender,
                    )
                    duplicate = _exact_patient(
                        cur,
                        last_name=patient_data["last_name"],
                        first_name=patient_data["first_name"],
                        patronymic=patient_data["patronymic"],
                        birth_date=patient_data["birth_date"],
                        exclude_patient_id=current_patient_id,
                    )
                    if duplicate:
                        raise HTTPException(
                            status_code=409,
                            detail="Такой пациент уже есть в базе. Выберите его из подсказки поиска.",
                        )
                    cur.execute(
                        """
                        UPDATE patients
                        SET last_name = %s, first_name = %s, patronymic = %s,
                            birth_date = %s, gender = %s, phone = %s
                        WHERE id = %s
                        """,
                        (
                            patient_data["last_name"],
                            patient_data["first_name"],
                            patient_data["patronymic"],
                            patient_data["birth_date"],
                            patient_data["gender"],
                            patient_data["phone"],
                            current_patient_id,
                        ),
                    )
                    target_patient_id = current_patient_id
                else:
                    patient_data = _validated_patient_data(
                        last_name=last_name,
                        first_name=first_name,
                        patronymic=patronymic,
                        birth_date=birth_date,
                        phone=phone,
                        gender=gender,
                    )
                    target_patient_id = _create_patient_from_schedule(cur, patient_data)

                appointment_type = (
                    "repeat" if _patient_has_appointments(cur, target_patient_id) else "primary"
                )
                _lock_doctor_day(cur, scheduled_doctor_id, starts_at.date())
                overlap = _find_overlap(
                    cur,
                    doctor_id=scheduled_doctor_id,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    exclude_entry_id=entry_id,
                )
                if overlap:
                    raise _overlap_error(overlap)
                cur.execute(
                    """
                    UPDATE schedule_entries
                    SET scheduled_doctor_id = %s,
                        location_id = %s,
                        patient_id = %s,
                        appointment_type = %s,
                        starts_at = %s,
                        ends_at = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        scheduled_doctor_id,
                        location_id,
                        target_patient_id,
                        appointment_type,
                        starts_at,
                        ends_at,
                        entry_id,
                    ),
                )
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Не удалось изменить запись: {exc}") from exc
    return get_schedule_entry(entry_id)


def set_schedule_entry_status(
    *, entry_id: int, status: str, user_id: int | None, cancel_reason: str | None = None
) -> dict[str, Any]:
    if status not in {"no_show", "cancelled"}:
        raise HTTPException(
            status_code=400,
            detail="Статус «Пришёл» устанавливается автоматически после сохранения приёма",
        )
    with get_db_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, appointment_id FROM schedule_entries WHERE id = %s FOR UPDATE",
                    (entry_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Запись не найдена")
                if status == "cancelled" and row["appointment_id"]:
                    raise HTTPException(status_code=409, detail="Нельзя отменить запись после сохранения медицинского приёма")
                cur.execute(
                    """
                    UPDATE schedule_entries
                    SET status = %s,
                        cancelled_at = CASE WHEN %s = 'cancelled' THEN CURRENT_TIMESTAMP ELSE NULL END,
                        cancelled_by_user_id = CASE WHEN %s = 'cancelled' THEN %s ELSE NULL END,
                        cancel_reason = CASE WHEN %s = 'cancelled' THEN %s ELSE NULL END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (status, status, status, user_id, status, _clean(cancel_reason) or None, entry_id),
                )
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Не удалось изменить статус: {exc}") from exc
    return get_schedule_entry(entry_id)


def get_schedule_entry_for_appointment_form(
    entry_id: int,
    patient_id: int | None = None,
) -> dict[str, Any]:
    item = get_schedule_entry(entry_id)
    if patient_id is not None and int(item["patient_id"]) != patient_id:
        raise HTTPException(status_code=403, detail="Запись принадлежит другому пациенту")
    if item["status"] == "cancelled":
        raise HTTPException(status_code=409, detail="Запись отменена")
    if item.get("appointment_id"):
        raise HTTPException(status_code=409, detail="Медицинский приём по этой записи уже сохранён")
    return item


def lock_schedule_entry_for_appointment(
    cur: Any, *, entry_id: int, patient_id: int
) -> dict[str, Any]:
    cur.execute(
        """
        SELECT id, patient_id, location_id, status, appointment_id
        FROM schedule_entries
        WHERE id = %s
        FOR UPDATE
        """,
        (entry_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Запись расписания не найдена")
    if int(row["patient_id"]) != patient_id:
        raise HTTPException(status_code=403, detail="Запись принадлежит другому пациенту")
    if row["status"] == "cancelled":
        raise HTTPException(status_code=409, detail="Запись отменена")
    if row["appointment_id"]:
        raise HTTPException(status_code=409, detail="Медицинский приём по этой записи уже создан")
    return dict(row)


def link_schedule_entry_to_appointment(
    cur: Any,
    *,
    entry_id: int,
    appointment_id: int,
    actual_doctor_id: int,
) -> None:
    cur.execute(
        """
        UPDATE schedule_entries
        SET appointment_id = %s,
            actual_doctor_id = %s,
            status = 'arrived',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (appointment_id, actual_doctor_id, entry_id),
    )

def get_patient_upcoming_schedule_entry(
    *,
    patient_id: int,
    now: datetime | None = None,
    days: int = 30,
) -> dict[str, Any] | None:
    """Возвращает ближайшую активную запись пациента на следующие ``days`` дней."""
    current = (now or datetime.now()).replace(microsecond=0)
    horizon = current + timedelta(days=max(1, min(int(days), 90)))
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM schedule_entries
                WHERE patient_id = %s
                  AND status = 'booked'
                  AND appointment_id IS NULL
                  AND ends_at > %s
                  AND starts_at <= %s
                ORDER BY starts_at, id
                LIMIT 1
                """,
                (patient_id, current, horizon),
            )
            row = cur.fetchone()
    return get_schedule_entry(int(row["id"])) if row else None


def _walk_in_times(now: datetime) -> tuple[datetime, datetime]:
    """Округляет начало вниз до пяти минут и задаёт стандартную длительность."""
    starts_at = now.replace(
        minute=(now.minute // 5) * 5,
        second=0,
        microsecond=0,
    )
    ends_at = starts_at + timedelta(minutes=WALK_IN_DURATION_MINUTES)
    if ends_at.date() != starts_at.date():
        ends_at = datetime.combine(starts_at.date(), time(23, 59))
    return starts_at, ends_at


def _resolve_walk_in_location(
    cur: Any,
    *,
    doctor_id: int,
    now: datetime,
    preferred_location_id: int | None,
) -> int:
    if preferred_location_id and _doctor_location_allowed(cur, doctor_id, preferred_location_id):
        return int(preferred_location_id)

    cur.execute(
        """
        SELECT e.location_id
        FROM schedule_entries e
        JOIN doctor_locations dl
          ON dl.doctor_id = e.scheduled_doctor_id
         AND dl.location_id = e.location_id
        WHERE e.scheduled_doctor_id = %s
          AND e.status <> 'cancelled'
          AND e.starts_at >= %s::date
          AND e.starts_at < (%s::date + INTERVAL '1 day')
        ORDER BY
          CASE WHEN e.starts_at <= %s AND e.ends_at > %s THEN 0 ELSE 1 END,
          ABS(EXTRACT(EPOCH FROM (e.starts_at - %s))),
          e.id
        LIMIT 1
        """,
        (doctor_id, now, now, now, now, now),
    )
    row = cur.fetchone()
    if row:
        return int(row["location_id"])

    cur.execute(
        """
        SELECT location_id
        FROM doctor_locations
        WHERE doctor_id = %s
        ORDER BY location_id
        LIMIT 1
        """,
        (doctor_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(
            status_code=409,
            detail="Для врача не настроено место приёма",
        )
    return int(row["location_id"])


def create_walk_in_schedule_entry(
    *,
    patient_id: int,
    doctor_id: int,
    created_by_user_id: int | None,
    cancel_entry_id: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Создаёт внеплановую запись, намеренно разрешая пересечение по времени."""
    current = (now or datetime.now()).replace(microsecond=0)
    starts_at, ends_at = _walk_in_times(current)
    entry_id: int

    with get_db_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM patients WHERE id = %s FOR SHARE",
                    (patient_id,),
                )
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="Пациент не найден")

                _lock_doctor_day(cur, doctor_id, starts_at.date())

                # Повторная отправка в ту же пятиминутку не создаёт дубликат.
                cur.execute(
                    """
                    SELECT id
                    FROM schedule_entries
                    WHERE scheduled_doctor_id = %s
                      AND patient_id = %s
                      AND starts_at = %s
                      AND status = 'booked'
                      AND appointment_id IS NULL
                      AND note = %s
                    ORDER BY id DESC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (doctor_id, patient_id, starts_at, WALK_IN_NOTE),
                )
                existing = cur.fetchone()
                if existing:
                    entry_id = int(existing["id"])
                else:
                    preferred_location_id: int | None = None
                    if cancel_entry_id is not None:
                        cur.execute(
                            """
                            SELECT id, patient_id, scheduled_doctor_id, location_id,
                                   starts_at, ends_at, status, appointment_id
                            FROM schedule_entries
                            WHERE id = %s
                            FOR UPDATE
                            """,
                            (cancel_entry_id,),
                        )
                        scheduled = cur.fetchone()
                        if not scheduled:
                            raise HTTPException(
                                status_code=409,
                                detail="Запланированная запись уже была изменена",
                            )
                        if int(scheduled["patient_id"]) != patient_id:
                            raise HTTPException(
                                status_code=403,
                                detail="Запись принадлежит другому пациенту",
                            )
                        if scheduled["status"] != "booked" or scheduled["appointment_id"]:
                            raise HTTPException(
                                status_code=409,
                                detail="Запланированную запись уже нельзя отменить",
                            )
                        if scheduled["ends_at"] <= current:
                            raise HTTPException(
                                status_code=409,
                                detail="Запланированная запись уже завершилась",
                            )
                        preferred_location_id = int(scheduled["location_id"])
                        # Для выбранного сценария старая запись должна исчезнуть из расписания.
                        cur.execute("DELETE FROM schedule_entries WHERE id = %s", (cancel_entry_id,))

                    location_id = _resolve_walk_in_location(
                        cur,
                        doctor_id=doctor_id,
                        now=current,
                        preferred_location_id=preferred_location_id,
                    )
                    appointment_type = (
                        "repeat" if _patient_has_appointments(cur, patient_id) else "primary"
                    )
                    cur.execute(
                        """
                        INSERT INTO schedule_entries(
                            scheduled_doctor_id, location_id, patient_id,
                            starts_at, ends_at, appointment_type, status, note,
                            created_by_user_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, 'booked', %s, %s)
                        RETURNING id
                        """,
                        (
                            doctor_id,
                            location_id,
                            patient_id,
                            starts_at,
                            ends_at,
                            appointment_type,
                            WALK_IN_NOTE,
                            created_by_user_id,
                        ),
                    )
                    entry_id = int(cur.fetchone()["id"])
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Не удалось создать внеплановый приём: {exc}",
            ) from exc

    return get_schedule_entry(entry_id)

