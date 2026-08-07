"""Real browser regression for eGFR -> ACR -> KDIGO recalculation."""
from __future__ import annotations

import os
from contextlib import contextmanager

import pytest

pytestmark = pytest.mark.browser


def _base_url() -> str:
    return os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


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
    if password.count() == 0:
        return
    login_value = os.getenv("E2E_LOGIN")
    password_value = os.getenv("E2E_PASSWORD")
    if not login_value or not password_value:
        pytest.skip("Page requires login. Set E2E_LOGIN and E2E_PASSWORD.")
    login = page.locator('input[name="login"], input[name="username"], input[type="text"]').first
    login.fill(login_value)
    password.first.fill(password_value)
    page.locator('button[type="submit"], input[type="submit"]').first.click()
    page.wait_for_load_state("domcontentloaded")
    page.goto(target, wait_until="domcontentloaded")


def _wait_until(page, predicate, message: str, timeout_ms: int = 5000):
    elapsed = 0
    while elapsed < timeout_ms:
        if predicate():
            return
        page.wait_for_timeout(100)
        elapsed += 100
    pytest.fail(message)


def _existing_patient_id() -> str:
    configured = os.getenv("E2E_EXISTING_PATIENT_ID")
    if configured:
        return configured
    try:
        from app.db.connection import get_db_connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM patients "
                    "WHERE birth_date IS NOT NULL AND gender IS NOT NULL "
                    "ORDER BY id LIMIT 1"
                )
                row = cur.fetchone()
    except Exception as exc:
        pytest.skip(f"Could not select a browser-test patient: {exc}")
    if not row:
        pytest.skip("Test DB needs one patient with birth date and gender.")
    if isinstance(row, dict):
        return str(row["id"])
    try:
        return str(row["id"])
    except (TypeError, KeyError):
        return str(row[0])


def test_existing_patient_form_recalculates_egfr_acr_and_kdigo_after_changes():
    patient_id = _existing_patient_id()

    with _browser_page() as page:
        _goto_with_login(page, f"/new-appointment/{patient_id}")
        root = page.locator("#kdigoRiskPreview")
        assert root.count() == 1
        assert root.get_attribute("data-patient-birth-date")
        assert root.get_attribute("data-patient-gender") not in {None, ""}

        page.locator("#addBiochemistryColumnBtn").click()
        creatinine = page.locator('#bio_creatinine_row input[name="creatinine"]').last
        creatinine.fill("80")
        stage = page.locator("#ckdStageRow .kidney-preview-metrics").last
        egfr = page.locator("#egfrRow .kidney-preview-metrics").last
        _wait_until(page, lambda: egfr.count() and egfr.text_content().strip() not in {"", "—"}, "eGFR was not calculated")
        first_stage = stage.text_content().strip()
        first_egfr = egfr.text_content().strip()

        creatinine.fill("400")
        _wait_until(page, lambda: egfr.text_content().strip() != first_egfr, "eGFR did not change after creatinine change")
        _wait_until(page, lambda: stage.text_content().strip() != first_stage, "CKD category did not change after creatinine change")

        page.locator("#addAlbuminuriaColumnBtn").click()
        albumin = page.locator('[data-albuminuria-column][data-field="albumin"]').last
        urine_creatinine = page.locator('[data-albuminuria-column][data-field="creatinine"]').last
        acr = page.locator('[data-albuminuria-column][data-field="acr"]').last
        category = page.locator('[data-albuminuria-column][data-field="category"]').last
        albumin.fill("234")
        urine_creatinine.fill("43")
        _wait_until(page, lambda: acr.input_value() in {"5.44", "5,44"}, "ACR 234/43 was not recalculated to 5.44")
        _wait_until(page, lambda: category.input_value() == "A2", "Albuminuria category A2 was not set")

        submitted = page.locator("form").evaluate(
            "form => ({creatinine: new FormData(form).getAll('creatinine'), "
            "albumin: new FormData(form).getAll('urine_albumin'), "
            "urineCreatinine: new FormData(form).getAll('urine_creatinine')})"
        )
        assert "400" in submitted["creatinine"]
        assert "234" in submitted["albumin"]
        assert "43" in submitted["urineCreatinine"]

        kdigo_text = page.locator("#kdigoCurrentVisitOptions").inner_text()
        _wait_until(
            page,
            lambda: "A2" in page.locator("#kdigoCurrentVisitOptions").inner_text() and "Невозможно" not in page.locator("#kdigoCurrentVisitOptions").inner_text(),
            "KDIGO was not calculated from current eGFR and A2",
        )
        kdigo_text = page.locator("#kdigoCurrentVisitOptions").inner_text()

        albumin.fill("20")
        _wait_until(page, lambda: category.input_value() == "A1", "Albuminuria category did not change to A1")
        _wait_until(page, lambda: "A1" in page.locator("#kdigoCurrentVisitOptions").inner_text(), "KDIGO did not update after albuminuria change")

        before_creatinine_change = page.locator("#kdigoCurrentVisitOptions").inner_text()
        creatinine.fill("80")
        _wait_until(
            page,
            lambda: page.locator("#kdigoCurrentVisitOptions").inner_text() != before_creatinine_change,
            "KDIGO did not update after creatinine/eGFR change",
        )
        assert page.locator("#kdigoCurrentVisitOptions").inner_text() != kdigo_text
