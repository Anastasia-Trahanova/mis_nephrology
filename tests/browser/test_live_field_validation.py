"""
Browser-тест живой валидации форм.

Запускается только если установлена переменная RUN_BROWSER_TESTS=1 и поднят сервер.
Проверяет пользовательский сценарий: врач вводит неверное значение, видит ошибку
рядом с полем, а форма не уходит на белую страницу с JSON.
"""

import os
import pytest

pytestmark = pytest.mark.browser


@pytest.mark.skipif(os.getenv("RUN_BROWSER_TESTS") != "1", reason="browser tests are opt-in")
def test_live_validation_marks_bad_pressure_before_submit(page):
    base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
    login = os.getenv("E2E_LOGIN")
    password = os.getenv("E2E_PASSWORD")
    patient_id = os.getenv("E2E_EXISTING_PATIENT_ID", "1")

    if login and password:
        page.goto(f"{base_url}/login")
        if page.locator("input[name='username']").count():
            page.fill("input[name='username']", login)
        if page.locator("input[name='password']").count():
            page.fill("input[name='password']", password)
        page.click("button[type='submit'], input[type='submit']")

    page.goto(f"{base_url}/new-appointment/{patient_id}")
    field = page.locator("input[name='systolic_pressure']").first
    field.fill("abc")
    field.blur()

    page.get_by_text("Неверное значение").wait_for(timeout=3000)
    assert "mis-field-invalid" in field.get_attribute("class") or "is-invalid" in field.get_attribute("class")
