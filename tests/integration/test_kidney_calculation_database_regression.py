"""DB regression: a repeated visit must persist creatinine, eGFR, ACR and KDIGO."""
from __future__ import annotations

import os
from datetime import date

import pytest
from starlette.datastructures import FormData

from app.db.connection import get_db_connection
from app.services.patient_appointment_service import create_appointment_for_existing_patient

pytestmark = pytest.mark.integration


def _enabled():
    if os.getenv("RUN_DB_LAYER_TESTS") != "1":
        pytest.skip("Set RUN_DB_LAYER_TESTS=1 to run DB integration tests.")


def _get(row, key, index=0):
    if isinstance(row, dict):
        return row[key]
    try:
        return row[key]
    except (TypeError, KeyError):
        return row[index]


def test_repeat_visit_persists_creatinine_egfr_acr_and_kdigo():
    _enabled()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id
                FROM patients p
                WHERE p.birth_date IS NOT NULL AND p.gender IS NOT NULL
                ORDER BY p.id
                LIMIT 1
                """
            )
            patient = cur.fetchone()
            cur.execute(
                """
                SELECT dl.doctor_id, dl.location_id
                FROM doctor_locations dl
                ORDER BY dl.doctor_id, dl.location_id
                LIMIT 1
                """
            )
            doctor_location = cur.fetchone()
    if not patient or not doctor_location:
        pytest.skip("Test DB needs one patient with gender/birth date and one doctor-location link.")

    patient_id = int(_get(patient, "id", 0))
    doctor_id = int(_get(doctor_location, "doctor_id", 0))
    location_id = int(_get(doctor_location, "location_id", 1))
    investigation_date = date.today().isoformat()
    appointment_id = None

    form = FormData(
        [
            ("location_id", str(location_id)),
            ("appointment_date", investigation_date),
            ("appointment_time", "23:57"),
            ("weight", "70"),
            ("biochemistry_investigation_date", investigation_date),
            ("creatinine", "123"),
            ("albuminuria_investigation_date", investigation_date),
            ("urine_albumin", "234"),
            ("urine_albumin_unit", "mg_l"),
            ("urine_creatinine", "43"),
            ("urine_creatinine_unit", "mmol_l"),
        ]
    )

    try:
        result = create_appointment_for_existing_patient(
            patient_id,
            form,
            current_doctor_id=doctor_id,
        )
        appointment_id = result.appointment_id

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT creatinine, investigation_date FROM biochemistry_results WHERE appointment_id = %s ORDER BY id DESC LIMIT 1",
                    (appointment_id,),
                )
                biochemistry = cur.fetchone()
                cur.execute(
                    """
                    SELECT creatinine, egfr_ckdepi, ckd_stage, investigation_date
                    FROM calculated_metrics
                    WHERE appointment_id = %s
                    ORDER BY id DESC LIMIT 1
                    """,
                    (appointment_id,),
                )
                metric = cur.fetchone()
                cur.execute(
                    """
                    SELECT albumin_creatinine_ratio, albuminuria_category, investigation_date
                    FROM albuminuria_results
                    WHERE appointment_id = %s
                    ORDER BY id DESC LIMIT 1
                    """,
                    (appointment_id,),
                )
                albuminuria = cur.fetchone()
                cur.execute(
                    """
                    SELECT gfr_category, albuminuria_category, combined_category, prognosis_level
                    FROM ckd_prognosis_results
                    WHERE appointment_id = %s
                      AND is_active = TRUE
                      AND calculation_status = 'calculated'
                    ORDER BY display_order, id
                    LIMIT 1
                    """,
                    (appointment_id,),
                )
                kdigo = cur.fetchone()

        assert biochemistry is not None
        assert float(_get(biochemistry, "creatinine", 0)) == 123.0

        assert metric is not None
        assert float(_get(metric, "creatinine", 0)) == 123.0
        assert _get(metric, "egfr_ckdepi", 1) is not None
        stage = str(_get(metric, "ckd_stage", 2))
        assert stage in {"С1", "С2", "С3а", "С3б", "С4", "С5"}

        assert albuminuria is not None
        assert float(_get(albuminuria, "albumin_creatinine_ratio", 0)) == pytest.approx(5.44, abs=0.01)
        assert _get(albuminuria, "albuminuria_category", 1) == "A2"

        assert kdigo is not None
        assert _get(kdigo, "gfr_category", 0) == stage
        assert _get(kdigo, "albuminuria_category", 1) == "A2"
        assert _get(kdigo, "combined_category", 2) == f"{stage}A2"
        assert _get(kdigo, "prognosis_level", 3) in {"low", "moderate", "high", "very_high"}
    finally:
        if appointment_id is not None:
            with get_db_connection() as conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM appointments WHERE id = %s", (appointment_id,))
                    conn.commit()
                except Exception:
                    conn.rollback()
