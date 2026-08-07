"""Database integration tests for server-side kidney preview persistence.

These tests create an isolated patient in the configured TEST database and remove
that patient (and all appointments created for it) after every test.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.datastructures import FormData

from app.db.connection import get_db_connection
from app.repositories.patients import create_patient
from app.services.patient_appointment_service import create_appointment_for_existing_patient


def _enabled() -> None:
    if os.getenv("RUN_DB_LAYER_TESTS") != "1":
        pytest.skip("Set RUN_DB_LAYER_TESTS=1 to run DB integration tests.")


def _row_value(row, key, index=0):
    if isinstance(row, dict):
        return row[key]
    try:
        return row[key]
    except (TypeError, KeyError):
        return row[index]


def _assert_test_database() -> str:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database() AS name")
            row = cur.fetchone()
    db_name = str(_row_value(row, "name", 0))
    if "test" not in db_name.lower():
        pytest.fail(
            f"Refusing to run write tests against database {db_name!r}. "
            "Use a dedicated database whose name contains 'test'."
        )
    return db_name


def _doctor_location():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT dl.doctor_id, dl.location_id
                FROM doctor_locations dl
                ORDER BY dl.doctor_id, dl.location_id
                LIMIT 1
                """
            )
            row = cur.fetchone()
    if not row:
        pytest.skip("Test DB needs one doctor-location link.")
    return int(_row_value(row, "doctor_id", 0)), int(_row_value(row, "location_id", 1))


@pytest.fixture
def db_case():
    _enabled()
    _assert_test_database()
    doctor_id, location_id = _doctor_location()

    suffix = uuid4().hex[:10]
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            patient_id = create_patient(
                cur,
                {
                    "last_name": f"KDIGO_TEST_{suffix}",
                    "first_name": "Автотест",
                    "patronymic": None,
                    "birth_date": date(1975, 1, 15),
                    "gender": False,
                    "phone": None,
                },
            )
        conn.commit()

    case = {
        "patient_id": int(patient_id),
        "doctor_id": doctor_id,
        "location_id": location_id,
    }
    try:
        yield case
    finally:
        with get_db_connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM appointments WHERE patient_id = %s", (case["patient_id"],))
                    cur.execute("DELETE FROM patients WHERE id = %s", (case["patient_id"],))
                conn.commit()
            except Exception:
                conn.rollback()
                raise


def _form(
    case,
    *,
    appointment_day: date,
    biochemistry=None,
    albuminuria=None,
    selected_pair: str | None = None,
    appointment_time: str = "12:00",
):
    entries = [
        ("location_id", str(case["location_id"])),
        ("appointment_date", appointment_day.isoformat()),
        ("appointment_time", appointment_time),
        ("weight", "70"),
    ]

    for item in biochemistry or []:
        entries.extend(
            [
                ("biochemistry_investigation_date", item.get("date", appointment_day.isoformat())),
                ("creatinine", str(item.get("creatinine", ""))),
            ]
        )

    for item in albuminuria or []:
        entries.extend(
            [
                ("albuminuria_investigation_date", item.get("date", appointment_day.isoformat())),
                ("urine_albumin", str(item.get("albumin", ""))),
                ("urine_albumin_unit", item.get("albumin_unit", "mg_l")),
                ("urine_creatinine", str(item.get("urine_creatinine", ""))),
                ("urine_creatinine_unit", item.get("urine_creatinine_unit", "mmol_l")),
                ("daily_albumin_excretion", str(item.get("daily", ""))),
            ]
        )

    if selected_pair is not None:
        entries.append(("kdigo_selected_pair", selected_pair))
    return FormData(entries)


def _create(case, form: FormData) -> int:
    result = create_appointment_for_existing_patient(
        case["patient_id"],
        form,
        current_doctor_id=case["doctor_id"],
    )
    return int(result.appointment_id)


def _fetchall(query: str, params):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def _count(table: str, appointment_id: int) -> int:
    rows = _fetchall(f"SELECT COUNT(*) AS n FROM {table} WHERE appointment_id = %s", (appointment_id,))
    return int(_row_value(rows[0], "n", 0))


def _appointment_count(patient_id: int) -> int:
    rows = _fetchall("SELECT COUNT(*) AS n FROM appointments WHERE patient_id = %s", (patient_id,))
    return int(_row_value(rows[0], "n", 0))


def test_visit_without_new_kidney_data_persists_no_new_kidney_rows_or_kdigo(db_case):
    day = date.today() - timedelta(days=1)

    appointment_id = _create(db_case, _form(db_case, appointment_day=day))

    assert _count("biochemistry_results", appointment_id) == 0
    assert _count("calculated_metrics", appointment_id) == 0
    assert _count("albuminuria_results", appointment_id) == 0
    assert _count("ckd_prognosis_results", appointment_id) == 0


def test_single_gfr_and_single_albuminuria_persist_all_calculations_and_one_kdigo(db_case):
    day = date.today() - timedelta(days=1)
    appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=day,
            biochemistry=[{"creatinine": 123}],
            albuminuria=[{"albumin": 234, "urine_creatinine": 43}],
        ),
    )

    assert _count("biochemistry_results", appointment_id) == 1
    assert _count("calculated_metrics", appointment_id) == 1
    assert _count("albuminuria_results", appointment_id) == 1
    assert _count("ckd_prognosis_results", appointment_id) == 1

    metric = _fetchall(
        "SELECT id, creatinine, egfr_ckdepi, ckd_stage FROM calculated_metrics WHERE appointment_id = %s",
        (appointment_id,),
    )[0]
    albuminuria = _fetchall(
        "SELECT id, albumin_creatinine_ratio, albuminuria_category FROM albuminuria_results WHERE appointment_id = %s",
        (appointment_id,),
    )[0]
    kdigo = _fetchall(
        """
        SELECT gfr_metric_id, albuminuria_result_id, gfr_category,
               albuminuria_category, combined_category, prognosis_level
        FROM ckd_prognosis_results
        WHERE appointment_id = %s AND is_active = TRUE AND calculation_status = 'calculated'
        """,
        (appointment_id,),
    )[0]

    assert float(_row_value(metric, "creatinine", 1)) == 123.0
    assert _row_value(metric, "egfr_ckdepi", 2) is not None
    assert _row_value(metric, "ckd_stage", 3) in {"С1", "С2", "С3а", "С3б", "С4", "С5"}
    assert float(_row_value(albuminuria, "albumin_creatinine_ratio", 1)) == pytest.approx(5.44, abs=0.01)
    assert _row_value(albuminuria, "albuminuria_category", 2) == "A2"
    assert int(_row_value(kdigo, "gfr_metric_id", 0)) == int(_row_value(metric, "id", 0))
    assert int(_row_value(kdigo, "albuminuria_result_id", 1)) == int(_row_value(albuminuria, "id", 0))
    assert _row_value(kdigo, "combined_category", 4) == f"{_row_value(metric, 'ckd_stage', 3)}A2"


def test_two_by_two_saves_every_source_but_only_explicitly_selected_kdigo_pair(db_case):
    day = date.today() - timedelta(days=1)
    selected = "gfr:current:1||albuminuria:current:0"
    appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=day,
            biochemistry=[{"creatinine": 80}, {"creatinine": 400}],
            albuminuria=[
                {"albumin": 20, "urine_creatinine": 43},
                {"albumin": 2000, "urine_creatinine": 43},
            ],
            selected_pair=selected,
        ),
    )

    assert _count("biochemistry_results", appointment_id) == 2
    assert _count("calculated_metrics", appointment_id) == 2
    assert _count("albuminuria_results", appointment_id) == 2
    assert _count("ckd_prognosis_results", appointment_id) == 1

    metrics = _fetchall(
        "SELECT id, creatinine, ckd_stage FROM calculated_metrics WHERE appointment_id = %s ORDER BY id",
        (appointment_id,),
    )
    albuminuria = _fetchall(
        "SELECT id, albuminuria_category FROM albuminuria_results WHERE appointment_id = %s ORDER BY id",
        (appointment_id,),
    )
    kdigo = _fetchall(
        """
        SELECT gfr_metric_id, albuminuria_result_id, gfr_category,
               albuminuria_category, combined_category
        FROM ckd_prognosis_results
        WHERE appointment_id = %s AND is_active = TRUE AND calculation_status = 'calculated'
        """,
        (appointment_id,),
    )[0]

    assert int(_row_value(kdigo, "gfr_metric_id", 0)) == int(_row_value(metrics[1], "id", 0))
    assert int(_row_value(kdigo, "albuminuria_result_id", 1)) == int(_row_value(albuminuria[0], "id", 0))
    assert _row_value(kdigo, "gfr_category", 2) == _row_value(metrics[1], "ckd_stage", 2)
    assert _row_value(kdigo, "albuminuria_category", 3) == _row_value(albuminuria[0], "albuminuria_category", 1)
    assert _row_value(kdigo, "combined_category", 4) == (
        f"{_row_value(metrics[1], 'ckd_stage', 2)}{_row_value(albuminuria[0], 'albuminuria_category', 1)}"
    )


def test_multiple_kdigo_candidates_without_selection_roll_back_entire_appointment(db_case):
    day = date.today() - timedelta(days=1)
    before = _appointment_count(db_case["patient_id"])

    with pytest.raises(HTTPException) as exc_info:
        _create(
            db_case,
            _form(
                db_case,
                appointment_day=day,
                biochemistry=[{"creatinine": 80}, {"creatinine": 400}],
                albuminuria=[{"albumin": 234, "urine_creatinine": 43}],
            ),
        )

    assert exc_info.value.status_code == 400
    assert "Выберите один вариант прогноза KDIGO" in str(exc_info.value.detail)
    assert _appointment_count(db_case["patient_id"]) == before


def test_tampered_selected_pair_rolls_back_entire_appointment(db_case):
    day = date.today() - timedelta(days=1)
    before = _appointment_count(db_case["patient_id"])

    with pytest.raises(HTTPException) as exc_info:
        _create(
            db_case,
            _form(
                db_case,
                appointment_day=day,
                biochemistry=[{"creatinine": 80}, {"creatinine": 400}],
                albuminuria=[{"albumin": 234, "urine_creatinine": 43}],
                selected_pair="gfr:current:999||albuminuria:current:999",
            ),
        )

    assert exc_info.value.status_code == 400
    assert "не соответствует текущим анализам" in str(exc_info.value.detail)
    assert _appointment_count(db_case["patient_id"]) == before


def test_new_gfr_uses_previous_saved_albuminuria_and_persists_source_reference(db_case):
    current_day = date.today() - timedelta(days=1)
    previous_day = current_day - timedelta(days=10)
    previous_appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=previous_day,
            albuminuria=[{"albumin": 234, "urine_creatinine": 43}],
        ),
    )
    previous_albuminuria = _fetchall(
        "SELECT id FROM albuminuria_results WHERE appointment_id = %s",
        (previous_appointment_id,),
    )[0]

    current_appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=current_day,
            biochemistry=[{"creatinine": 123}],
        ),
    )
    kdigo = _fetchall(
        """
        SELECT albuminuria_result_id, albuminuria_source_type, albuminuria_category
        FROM ckd_prognosis_results
        WHERE appointment_id = %s AND is_active = TRUE AND calculation_status = 'calculated'
        """,
        (current_appointment_id,),
    )[0]

    assert int(_row_value(kdigo, "albuminuria_result_id", 0)) == int(_row_value(previous_albuminuria, "id", 0))
    assert _row_value(kdigo, "albuminuria_source_type", 1) == "previous_appointment"
    assert _row_value(kdigo, "albuminuria_category", 2) == "A2"


def test_new_albuminuria_uses_previous_saved_gfr_and_persists_source_reference(db_case):
    current_day = date.today() - timedelta(days=1)
    previous_day = current_day - timedelta(days=10)
    previous_appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=previous_day,
            biochemistry=[{"creatinine": 123}],
        ),
    )
    previous_metric = _fetchall(
        "SELECT id, ckd_stage FROM calculated_metrics WHERE appointment_id = %s",
        (previous_appointment_id,),
    )[0]

    current_appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=current_day,
            albuminuria=[{"albumin": 234, "urine_creatinine": 43}],
        ),
    )
    kdigo = _fetchall(
        """
        SELECT gfr_metric_id, gfr_source_type, gfr_category
        FROM ckd_prognosis_results
        WHERE appointment_id = %s AND is_active = TRUE AND calculation_status = 'calculated'
        """,
        (current_appointment_id,),
    )[0]

    assert int(_row_value(kdigo, "gfr_metric_id", 0)) == int(_row_value(previous_metric, "id", 0))
    assert _row_value(kdigo, "gfr_source_type", 1) == "previous_appointment"
    assert _row_value(kdigo, "gfr_category", 2) == _row_value(previous_metric, "ckd_stage", 1)


def test_stale_previous_albuminuria_does_not_create_saved_kdigo(db_case):
    current_day = date.today() - timedelta(days=1)
    stale_day = current_day - timedelta(days=91)
    _create(
        db_case,
        _form(
            db_case,
            appointment_day=stale_day,
            albuminuria=[{"albumin": 234, "urine_creatinine": 43}],
        ),
    )

    current_appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=current_day,
            biochemistry=[{"creatinine": 400}],
        ),
    )

    assert _count("calculated_metrics", current_appointment_id) == 1
    assert _count("ckd_prognosis_results", current_appointment_id) == 0


def test_daily_albumin_excretion_is_persisted_and_can_drive_kdigo_without_acr(db_case):
    day = date.today() - timedelta(days=1)
    appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=day,
            biochemistry=[{"creatinine": 123}],
            albuminuria=[{"daily": 100}],
        ),
    )

    albuminuria = _fetchall(
        """
        SELECT albumin_creatinine_ratio, daily_albumin_excretion, albuminuria_category
        FROM albuminuria_results WHERE appointment_id = %s
        """,
        (appointment_id,),
    )[0]
    kdigo = _fetchall(
        "SELECT albuminuria_category FROM ckd_prognosis_results WHERE appointment_id = %s",
        (appointment_id,),
    )[0]

    assert _row_value(albuminuria, "albumin_creatinine_ratio", 0) is None
    assert float(_row_value(albuminuria, "daily_albumin_excretion", 1)) == 100.0
    assert _row_value(albuminuria, "albuminuria_category", 2) == "A2"
    assert _row_value(kdigo, "albuminuria_category", 0) == "A2"


def test_visit_after_saved_kdigo_without_new_kidney_data_does_not_copy_old_prognosis(db_case):
    current_day = date.today() - timedelta(days=1)
    previous_day = current_day - timedelta(days=10)
    previous_appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=previous_day,
            biochemistry=[{"creatinine": 123}],
            albuminuria=[{"albumin": 234, "urine_creatinine": 43}],
        ),
    )
    assert _count("ckd_prognosis_results", previous_appointment_id) == 1

    current_appointment_id = _create(
        db_case,
        _form(db_case, appointment_day=current_day),
    )

    assert _count("calculated_metrics", current_appointment_id) == 0
    assert _count("albuminuria_results", current_appointment_id) == 0
    assert _count("ckd_prognosis_results", current_appointment_id) == 0


def test_albuminuria_unit_conversion_is_persisted_using_server_result(db_case):
    day = date.today() - timedelta(days=1)
    appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=day,
            biochemistry=[{"creatinine": 123}],
            albuminuria=[
                {
                    "albumin": 0.234,
                    "albumin_unit": "g_l",
                    "urine_creatinine": 43000,
                    "urine_creatinine_unit": "umol_l",
                }
            ],
        ),
    )

    row = _fetchall(
        """
        SELECT albumin_creatinine_ratio, albuminuria_category
        FROM albuminuria_results WHERE appointment_id = %s
        """,
        (appointment_id,),
    )[0]
    assert float(_row_value(row, "albumin_creatinine_ratio", 0)) == pytest.approx(5.44, abs=0.01)
    assert _row_value(row, "albuminuria_category", 1) == "A2"
    assert _count("ckd_prognosis_results", appointment_id) == 1


def test_acr_category_has_persistence_priority_over_conflicting_daily_excretion(db_case):
    day = date.today() - timedelta(days=1)
    appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=day,
            biochemistry=[{"creatinine": 123}],
            albuminuria=[{"albumin": 20, "urine_creatinine": 43, "daily": 500}],
        ),
    )

    row = _fetchall(
        """
        SELECT albumin_creatinine_ratio, daily_albumin_excretion, albuminuria_category
        FROM albuminuria_results WHERE appointment_id = %s
        """,
        (appointment_id,),
    )[0]
    assert float(_row_value(row, "albumin_creatinine_ratio", 0)) < 3
    assert float(_row_value(row, "daily_albumin_excretion", 1)) == 500.0
    assert _row_value(row, "albuminuria_category", 2) == "A1"
    kdigo = _fetchall(
        "SELECT albuminuria_category FROM ckd_prognosis_results WHERE appointment_id = %s",
        (appointment_id,),
    )[0]
    assert _row_value(kdigo, "albuminuria_category", 0) == "A1"


def test_two_new_gfr_with_previous_albuminuria_require_and_persist_explicit_choice(db_case):
    current_day = date.today() - timedelta(days=1)
    previous_day = current_day - timedelta(days=10)
    previous_appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=previous_day,
            albuminuria=[{"albumin": 234, "urine_creatinine": 43}],
        ),
    )
    previous_albuminuria = _fetchall(
        "SELECT id, investigation_date, albuminuria_category FROM albuminuria_results WHERE appointment_id = %s",
        (previous_appointment_id,),
    )[0]
    previous_date = _row_value(previous_albuminuria, "investigation_date", 1).isoformat()
    previous_category = _row_value(previous_albuminuria, "albuminuria_category", 2)
    selected_pair = f"gfr:current:1||albuminuria:previous_appointment:{previous_date}:{previous_category}"

    appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=current_day,
            biochemistry=[{"creatinine": 80}, {"creatinine": 400}],
            selected_pair=selected_pair,
        ),
    )

    metrics = _fetchall(
        "SELECT id FROM calculated_metrics WHERE appointment_id = %s ORDER BY id",
        (appointment_id,),
    )
    kdigo = _fetchall(
        "SELECT gfr_metric_id, albuminuria_result_id FROM ckd_prognosis_results WHERE appointment_id = %s",
        (appointment_id,),
    )[0]
    assert len(metrics) == 2
    assert _count("ckd_prognosis_results", appointment_id) == 1
    assert int(_row_value(kdigo, "gfr_metric_id", 0)) == int(_row_value(metrics[1], "id", 0))
    assert int(_row_value(kdigo, "albuminuria_result_id", 1)) == int(
        _row_value(previous_albuminuria, "id", 0)
    )


def test_two_new_albuminuria_with_previous_gfr_require_and_persist_explicit_choice(db_case):
    current_day = date.today() - timedelta(days=1)
    previous_day = current_day - timedelta(days=10)
    previous_appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=previous_day,
            biochemistry=[{"creatinine": 123}],
        ),
    )
    previous_metric = _fetchall(
        "SELECT id, investigation_date, ckd_stage FROM calculated_metrics WHERE appointment_id = %s",
        (previous_appointment_id,),
    )[0]
    previous_date = _row_value(previous_metric, "investigation_date", 1).isoformat()
    previous_category = _row_value(previous_metric, "ckd_stage", 2)
    selected_pair = f"gfr:previous_appointment:{previous_date}:{previous_category}||albuminuria:current:1"

    appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=current_day,
            albuminuria=[
                {"albumin": 20, "urine_creatinine": 43},
                {"albumin": 2000, "urine_creatinine": 43},
            ],
            selected_pair=selected_pair,
        ),
    )

    albuminuria = _fetchall(
        "SELECT id FROM albuminuria_results WHERE appointment_id = %s ORDER BY id",
        (appointment_id,),
    )
    kdigo = _fetchall(
        "SELECT gfr_metric_id, albuminuria_result_id FROM ckd_prognosis_results WHERE appointment_id = %s",
        (appointment_id,),
    )[0]
    assert len(albuminuria) == 2
    assert _count("ckd_prognosis_results", appointment_id) == 1
    assert int(_row_value(kdigo, "gfr_metric_id", 0)) == int(_row_value(previous_metric, "id", 0))
    assert int(_row_value(kdigo, "albuminuria_result_id", 1)) == int(
        _row_value(albuminuria[1], "id", 0)
    )


def test_one_valid_and_one_stale_current_pair_auto_saves_only_valid_candidate(db_case):
    day = date.today() - timedelta(days=1)
    stale_gfr_day = day - timedelta(days=100)
    appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=day,
            biochemistry=[
                {"date": day.isoformat(), "creatinine": 400},
                {"date": stale_gfr_day.isoformat(), "creatinine": 400},
            ],
            albuminuria=[{"date": day.isoformat(), "albumin": 234, "urine_creatinine": 43}],
        ),
    )

    metrics = _fetchall(
        "SELECT id, investigation_date FROM calculated_metrics WHERE appointment_id = %s ORDER BY id",
        (appointment_id,),
    )
    kdigo = _fetchall(
        "SELECT gfr_metric_id, source_interval_days FROM ckd_prognosis_results WHERE appointment_id = %s",
        (appointment_id,),
    )[0]

    assert len(metrics) == 2
    assert _count("ckd_prognosis_results", appointment_id) == 1
    assert int(_row_value(kdigo, "gfr_metric_id", 0)) == int(_row_value(metrics[0], "id", 0))
    assert int(_row_value(kdigo, "source_interval_days", 1)) == 0


def test_selection_ordinals_stay_bound_to_form_insertion_order_when_dates_are_reversed(db_case):
    day = date.today() - timedelta(days=1)
    older = day - timedelta(days=5)
    selected_pair = "gfr:current:0||albuminuria:current:1"
    appointment_id = _create(
        db_case,
        _form(
            db_case,
            appointment_day=day,
            biochemistry=[
                {"date": day.isoformat(), "creatinine": 80},
                {"date": older.isoformat(), "creatinine": 400},
            ],
            albuminuria=[
                {"date": day.isoformat(), "albumin": 20, "urine_creatinine": 43},
                {"date": older.isoformat(), "albumin": 2000, "urine_creatinine": 43},
            ],
            selected_pair=selected_pair,
        ),
    )

    metrics = _fetchall(
        "SELECT id, investigation_date FROM calculated_metrics WHERE appointment_id = %s ORDER BY id",
        (appointment_id,),
    )
    albuminuria = _fetchall(
        "SELECT id, investigation_date FROM albuminuria_results WHERE appointment_id = %s ORDER BY id",
        (appointment_id,),
    )
    kdigo = _fetchall(
        "SELECT gfr_metric_id, albuminuria_result_id FROM ckd_prognosis_results WHERE appointment_id = %s",
        (appointment_id,),
    )[0]

    assert int(_row_value(kdigo, "gfr_metric_id", 0)) == int(_row_value(metrics[0], "id", 0))
    assert int(_row_value(kdigo, "albuminuria_result_id", 1)) == int(_row_value(albuminuria[1], "id", 0))
