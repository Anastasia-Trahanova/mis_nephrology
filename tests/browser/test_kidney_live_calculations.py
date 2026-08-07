"""Real-browser kidney workflow tests.

The tests create an isolated patient in a TEST database. They never run write
scenarios unless the connected database name contains ``test``.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, timedelta
from uuid import uuid4

import pytest
from starlette.datastructures import FormData

from app.db.connection import get_db_connection
from app.repositories.patients import create_patient
from app.services.patient_appointment_service import create_appointment_for_existing_patient


pytestmark = pytest.mark.browser




def _seed_saved_kdigo(patient_id: int) -> int:
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
            doctor_location = cur.fetchone()
    if not doctor_location:
        pytest.skip("Test DB needs one doctor-location link to seed KDIGO history.")

    doctor_id = int(_row_value(doctor_location, "doctor_id", 0))
    location_id = int(_row_value(doctor_location, "location_id", 1))
    day = date.today() - timedelta(days=5)
    form = FormData(
        [
            ("location_id", str(location_id)),
            ("appointment_date", day.isoformat()),
            ("appointment_time", "12:00"),
            ("weight", "70"),
            ("biochemistry_investigation_date", day.isoformat()),
            ("creatinine", "123"),
            ("albuminuria_investigation_date", day.isoformat()),
            ("urine_albumin", "234"),
            ("urine_albumin_unit", "mg_l"),
            ("urine_creatinine", "43"),
            ("urine_creatinine_unit", "mmol_l"),
        ]
    )
    result = create_appointment_for_existing_patient(
        patient_id,
        form,
        current_doctor_id=doctor_id,
    )
    return int(result.appointment_id)


def _base_url() -> str:
    return os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


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
            f"Refusing to run browser write tests against database {db_name!r}. "
            "Use a dedicated database whose name contains 'test'."
        )
    return db_name


@pytest.fixture
def browser_patient(browser_base_url):
    if os.getenv("RUN_BROWSER_TESTS") != "1":
        pytest.skip("Set RUN_BROWSER_TESTS=1 to run browser tests.")
    _assert_test_database()

    suffix = uuid4().hex[:10]
    last_name = f"KDIGO_E2E_{suffix}"
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            patient_id = create_patient(
                cur,
                {
                    "last_name": last_name,
                    "first_name": "Браузер",
                    "patronymic": None,
                    "birth_date": date(1975, 1, 15),
                    "gender": False,
                    "phone": None,
                },
            )
        conn.commit()

    patient = {"id": int(patient_id), "last_name": last_name}
    try:
        yield patient
    finally:
        with get_db_connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM appointments WHERE patient_id = %s", (patient["id"],))
                    cur.execute("DELETE FROM patients WHERE id = %s", (patient["id"],))
                conn.commit()
            except Exception:
                conn.rollback()
                raise


@contextmanager
def _browser_page():
    if os.getenv("RUN_BROWSER_TESTS") != "1":
        pytest.skip("Set RUN_BROWSER_TESTS=1 to run browser tests.")
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=os.getenv("E2E_HEADLESS", "1") != "0")
        page = browser.new_page()
        try:
            yield page
        finally:
            browser.close()


def _goto_with_login(page, path: str):
    target = f"{_base_url()}{path}"
    page.goto(target, wait_until="domcontentloaded")
    password = page.locator('input[type="password"], input[name="password"]')
    if password.count() > 0:
        login_value = (os.getenv("E2E_LOGIN") or "").strip()
        password_value = os.getenv("E2E_PASSWORD") or ""
        if not login_value or not password_value:
            pytest.skip("Page requires login. Set E2E_LOGIN and E2E_PASSWORD.")
        login = page.locator('input[name="login"], input[name="username"], input[type="text"]').first
        login.fill(login_value)
        password.first.fill(password_value)
        page.locator('button[type="submit"], input[type="submit"]').first.click()
        page.wait_for_load_state("domcontentloaded")
        page.goto(target, wait_until="domcontentloaded")

    if "/login" in page.url:
        pytest.fail(
            "Browser login did not succeed. Check E2E_LOGIN/E2E_PASSWORD; "
            "E2E_LOGIN must not contain a leading space."
        )


def _open_patient_form(page, patient):
    _goto_with_login(page, f"/new-appointment/{patient['id']}")
    if page.get_by_text(patient["last_name"], exact=False).count() == 0:
        pytest.fail(
            "The test patient is not visible in the opened form. The running FastAPI "
            "server and pytest may be connected to different databases."
        )
    root = page.locator("#kdigoRiskPreview")
    assert root.count() == 1
    return root


def _wait_until(page, predicate, message: str, timeout_ms: int = 8000):
    elapsed = 0
    while elapsed < timeout_ms:
        if predicate():
            return
        page.wait_for_timeout(100)
        elapsed += 100
    pytest.fail(message)


def _fill_save_required_fields(page):
    location = page.locator('select[name="location_id"]')
    assert location.count() == 1
    options = location.locator("option")
    if options.count() < 2:
        pytest.fail("Logged-in doctor has no selectable location in the appointment form.")
    location.select_option(index=1)

    safe_day = (date.today() - timedelta(days=1)).isoformat()
    page.locator('input[name="appointment_date"]').fill(safe_day)
    page.locator('input[name="appointment_time"]').fill("12:00")
    weight = page.locator('input[name="weight"]')
    if weight.count():
        weight.fill("70")
    return safe_day


def _add_biochemistry(page, creatinine_value: str, investigation_date: str):
    page.locator("#addBiochemistryColumnBtn").click()
    creatinine = page.locator('#bio_creatinine_row input[name="creatinine"]').last
    date_input = page.locator('input[name="biochemistry_investigation_date"]').last
    date_input.fill(investigation_date)
    creatinine.fill(creatinine_value)
    return creatinine


def _add_albuminuria(page, albumin_value: str, urine_creatinine_value: str, investigation_date: str):
    page.locator("#addAlbuminuriaColumnBtn").click()
    date_input = page.locator('input[name="albuminuria_investigation_date"]').last
    albumin = page.locator('[data-albuminuria-column][data-field="albumin"]').last
    urine_creatinine = page.locator('[data-albuminuria-column][data-field="creatinine"]').last
    acr = page.locator('[data-albuminuria-column][data-field="acr"]').last
    category = page.locator('[data-albuminuria-column][data-field="category"]').last
    date_input.fill(investigation_date)
    albumin.fill(albumin_value)
    urine_creatinine.fill(urine_creatinine_value)
    return albumin, urine_creatinine, acr, category


def _enabled_kdigo_radios(page):
    return page.locator('#kdigoCurrentVisitOptions input[type="radio"]:not([disabled])')


def _latest_appointment_id(patient_id: int) -> int | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM appointments WHERE patient_id = %s ORDER BY id DESC LIMIT 1",
                (patient_id,),
            )
            row = cur.fetchone()
    return int(_row_value(row, "id", 0)) if row else None


def _db_count(table: str, appointment_id: int) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE appointment_id = %s", (appointment_id,))
            row = cur.fetchone()
    return int(_row_value(row, "n", 0))


def _assert_patient_card_schema_current() -> None:
    """Fail clearly when the TEST DB cannot render the current patient card."""
    required = {
        "diagnosis_text",
        "diagnosis_comment_text",
        "is_archive_import",
        "archive_import_key",
        "archive_source_relative_path",
    }
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'appointments'
                """
            )
            existing = {str(_row_value(row, "column_name", 0)) for row in cur.fetchall()}
    missing = sorted(required - existing)
    if missing:
        pytest.fail(
            "The TEST database schema is older than the running application and "
            "cannot render the patient card. Missing appointments columns: "
            + ", ".join(missing)
            + ". This is a test-database schema problem, not a KDIGO calculation failure."
        )


def test_new_visit_with_saved_history_starts_without_current_kdigo_and_history_matrix_still_works(browser_patient):
    previous_appointment_id = _seed_saved_kdigo(browser_patient["id"])
    assert _db_count("ckd_prognosis_results", previous_appointment_id) == 1

    with _browser_page() as page:
        _open_patient_form(page, browser_patient)

        assert page.locator("#kdigoCurrentVisitOptions").inner_text().strip() == ""
        assert page.locator("#kdigoSelectedPair").input_value() == ""
        assert _enabled_kdigo_radios(page).count() == 0

        history_button = page.locator("#kdigoToggleHistoryButton")
        history_panel = page.locator("#kdigoHistoryPanel")
        assert history_button.count() == 1
        assert history_panel.is_hidden()
        history_button.click()
        assert history_panel.is_visible()
        assert history_panel.locator(".kdigo-history-risk").count() == 1


def test_live_server_preview_recalculates_gfr_acr_and_kdigo_after_each_change(browser_patient):
    with _browser_page() as page:
        _open_patient_form(page, browser_patient)
        safe_day = _fill_save_required_fields(page)

        creatinine = _add_biochemistry(page, "80", safe_day)
        egfr = page.locator("#egfrRow .kidney-preview-metrics").last
        stage = page.locator("#ckdStageRow .kidney-preview-metrics").last
        _wait_until(page, lambda: egfr.count() and egfr.text_content().strip() not in {"", "—"}, "eGFR was not calculated")
        _wait_until(page, lambda: stage.text_content().strip() == "С2", "Creatinine 80 did not produce С2")
        first_egfr = egfr.text_content().strip()

        creatinine.fill("400")
        _wait_until(page, lambda: egfr.text_content().strip() != first_egfr, "eGFR did not update after creatinine change")
        _wait_until(page, lambda: stage.text_content().strip() == "С5", "Creatinine 400 did not produce С5")

        albumin, _, acr, category = _add_albuminuria(page, "234", "43", safe_day)
        _wait_until(page, lambda: acr.input_value() in {"5.44", "5,44"}, "ACR 234/43 was not recalculated to 5.44")
        _wait_until(page, lambda: category.input_value() == "A2", "Albuminuria category A2 was not set")
        _wait_until(page, lambda: "С5A2" in page.locator("#kdigoCurrentVisitOptions").inner_text(), "KDIGO С5A2 was not calculated")
        _wait_until(page, lambda: _enabled_kdigo_radios(page).count() == 1, "Single KDIGO candidate did not render one radio")
        assert _enabled_kdigo_radios(page).first.is_checked()
        assert page.locator("#kdigoSelectedPair").input_value() == "gfr:current:0||albuminuria:current:0"

        albumin.fill("20")
        _wait_until(page, lambda: category.input_value() == "A1", "Albuminuria category did not update to A1")
        _wait_until(page, lambda: "С5A1" in page.locator("#kdigoCurrentVisitOptions").inner_text(), "KDIGO did not update after albuminuria change")

        creatinine.fill("80")
        _wait_until(page, lambda: stage.text_content().strip() == "С2", "CKD stage did not return to С2")
        _wait_until(page, lambda: "С2A1" in page.locator("#kdigoCurrentVisitOptions").inner_text(), "KDIGO did not update after creatinine change")


def test_two_by_two_shows_four_candidates_and_blocks_submit_until_doctor_selects_one(browser_patient):
    with _browser_page() as page:
        _open_patient_form(page, browser_patient)
        safe_day = _fill_save_required_fields(page)

        _add_biochemistry(page, "80", safe_day)
        _add_albuminuria(page, "20", "43", safe_day)
        _wait_until(page, lambda: _enabled_kdigo_radios(page).count() == 1, "Initial 1x1 KDIGO candidate did not appear")
        assert page.locator("#kdigoSelectedPair").input_value() == "gfr:current:0||albuminuria:current:0"

        _add_biochemistry(page, "400", safe_day)
        _wait_until(page, lambda: _enabled_kdigo_radios(page).count() == 2, "2 GFR x 1 albuminuria did not produce two candidates")
        _wait_until(page, lambda: page.locator("#kdigoSelectedPair").input_value() == "", "Automatic single-candidate choice was not cleared after a second source appeared")

        _add_albuminuria(page, "2000", "43", safe_day)

        radios = _enabled_kdigo_radios(page)
        _wait_until(page, lambda: radios.count() == 4, "2 GFR x 2 albuminuria did not produce four selectable KDIGO candidates")
        assert page.locator("#kdigoSelectedPair").input_value() == ""
        assert page.locator('[data-kdigo-selection-hint="1"]').count() == 1

        before_url = page.url
        page.get_by_role("button", name="Сохранить прием").click()
        page.wait_for_timeout(300)
        assert page.url == before_url
        assert page.locator('[data-kdigo-selection-hint="1"]').is_visible()

        target_key = "gfr:current:1||albuminuria:current:0"
        target = page.locator(f'#kdigoCurrentVisitOptions input[type="radio"][value="{target_key}"]')
        assert target.count() == 1
        target.check()
        assert page.locator("#kdigoSelectedPair").input_value() == target_key

        # Recalculation with the same set of sources must keep the explicit choice.
        page.locator('#bio_creatinine_row input[name="creatinine"]').last.fill("350")
        _wait_until(
            page,
            lambda: page.locator("#kdigoSelectedPair").input_value() == target_key,
            "Explicit KDIGO selection was lost after recalculation of the same source pair",
        )


def test_selected_two_by_two_visit_saves_all_sources_one_kdigo_and_card_matrix(browser_patient, browser_server_logs):
    _assert_patient_card_schema_current()
    with _browser_page() as page:
        _open_patient_form(page, browser_patient)
        safe_day = _fill_save_required_fields(page)

        _add_biochemistry(page, "80", safe_day)
        _add_biochemistry(page, "400", safe_day)
        _add_albuminuria(page, "20", "43", safe_day)
        _add_albuminuria(page, "2000", "43", safe_day)

        radios = _enabled_kdigo_radios(page)
        _wait_until(page, lambda: radios.count() == 4, "Four KDIGO candidates did not appear before save")
        target_key = "gfr:current:1||albuminuria:current:0"
        target = page.locator(f'#kdigoCurrentVisitOptions input[type="radio"][value="{target_key}"]')
        target.check()
        selected_label = target.locator("xpath=..").inner_text()

        page.get_by_role("button", name="Сохранить прием").click()
        page.wait_for_load_state("domcontentloaded")
        _wait_until(page, lambda: "/new-appointment/" not in page.url, "Appointment form did not leave the save page")

        appointment_id = _latest_appointment_id(browser_patient["id"])
        assert appointment_id is not None
        assert _db_count("biochemistry_results", appointment_id) == 2
        assert _db_count("calculated_metrics", appointment_id) == 2
        assert _db_count("albuminuria_results", appointment_id) == 2
        assert _db_count("ckd_prognosis_results", appointment_id) == 1

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT combined_category, prognosis_text
                    FROM ckd_prognosis_results
                    WHERE appointment_id = %s
                      AND is_active = TRUE
                      AND calculation_status = 'calculated'
                    """,
                    (appointment_id,),
                )
                kdigo = cur.fetchone()
        combined = str(_row_value(kdigo, "combined_category", 0))
        prognosis_text = str(_row_value(kdigo, "prognosis_text", 1))

        body_text = page.locator("body").inner_text()
        if "Internal Server Error" in body_text:
            logs = "\n".join(browser_server_logs()[-120:])
            pytest.fail(
                "Patient card returned Internal Server Error after a successful save. "
                "FastAPI output follows:\n" + (logs or "<no server output captured>")
            )
        assert combined in body_text
        assert prognosis_text in body_text
        assert combined in selected_label

        matrix_button = page.locator("#kdigoCardToggleMatrixButton")
        matrix_panel = page.locator("#kdigoCardMatrixPanel")
        assert matrix_button.count() == 1
        matrix_button.click()
        assert matrix_panel.is_visible()
        assert prognosis_text in matrix_panel.inner_text()
        assert matrix_panel.locator(".kdigo-card-risk").count() == 1


def test_new_gfr_uses_saved_previous_albuminuria_then_switches_to_current_albuminuria(browser_patient):
    _seed_saved_kdigo(browser_patient["id"])

    with _browser_page() as page:
        _open_patient_form(page, browser_patient)
        safe_day = _fill_save_required_fields(page)

        _add_biochemistry(page, "80", safe_day)
        _wait_until(page, lambda: _enabled_kdigo_radios(page).count() == 1, "New GFR did not combine with previous albuminuria")
        previous_pair = page.locator("#kdigoSelectedPair").input_value()
        assert previous_pair.startswith("gfr:current:0||albuminuria:previous_appointment:")
        assert previous_pair.endswith(":A2")

        _add_albuminuria(page, "2000", "43", safe_day)
        _wait_until(
            page,
            lambda: page.locator("#kdigoSelectedPair").input_value() == "gfr:current:0||albuminuria:current:0",
            "Current albuminuria did not replace previous albuminuria as the live KDIGO source",
        )
        assert "A3" in page.locator("#kdigoCurrentVisitOptions").inner_text()


def test_new_albuminuria_uses_saved_previous_gfr_when_no_current_creatinine_exists(browser_patient):
    _seed_saved_kdigo(browser_patient["id"])

    with _browser_page() as page:
        _open_patient_form(page, browser_patient)
        safe_day = _fill_save_required_fields(page)

        _add_albuminuria(page, "20", "43", safe_day)
        _wait_until(page, lambda: _enabled_kdigo_radios(page).count() == 1, "New albuminuria did not combine with previous GFR")
        selected_pair = page.locator("#kdigoSelectedPair").input_value()
        assert selected_pair.startswith("gfr:previous_appointment:")
        assert selected_pair.endswith("||albuminuria:current:0")
        assert "A1" in page.locator("#kdigoCurrentVisitOptions").inner_text()
