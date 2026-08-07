"""Browser test for live field validation.

Uses the local browser fixtures from tests/browser/conftest.py, so it does not
require pytest-playwright and does not depend on an externally started server.
"""
from __future__ import annotations

import os
from datetime import date
from uuid import uuid4

import pytest

from app.db.connection import get_db_connection
from app.repositories.patients import create_patient


pytestmark = pytest.mark.browser


def _goto_with_login(page, base_url: str, path: str):
    target = f"{base_url.rstrip('/')}{path}"
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
        pytest.fail("Browser login did not succeed. Check E2E_LOGIN/E2E_PASSWORD.")


@pytest.fixture
def validation_patient(browser_base_url):
    suffix = uuid4().hex[:10]
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            patient_id = create_patient(
                cur,
                {
                    "last_name": f"VALIDATION_E2E_{suffix}",
                    "first_name": "Проверка",
                    "patronymic": None,
                    "birth_date": date(1980, 1, 15),
                    "gender": False,
                    "phone": None,
                },
            )
        conn.commit()

    try:
        yield int(patient_id)
    finally:
        with get_db_connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM appointments WHERE patient_id = %s", (patient_id,))
                    cur.execute("DELETE FROM patients WHERE id = %s", (patient_id,))
                conn.commit()
            except Exception:
                conn.rollback()
                raise


@pytest.mark.skipif(os.getenv("RUN_BROWSER_TESTS") != "1", reason="browser tests are opt-in")
def test_live_validation_marks_bad_pressure_before_submit(page, browser_base_url, validation_patient):
    _goto_with_login(page, browser_base_url, f"/new-appointment/{validation_patient}")

    field = page.locator("input[name='systolic_pressure']").first
    assert field.count() == 1
    field.fill("abc")
    field.blur()

    page.get_by_text("Неверное значение").wait_for(timeout=3000)
    classes = field.get_attribute("class") or ""
    assert "mis-field-invalid" in classes or "is-invalid" in classes
