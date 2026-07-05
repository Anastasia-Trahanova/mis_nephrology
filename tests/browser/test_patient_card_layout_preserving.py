"""
Browser-тест карточки пациента после layout-preserving разбиения шаблона.

Что тестируется:
- реальная страница карточки открывается в браузере;
- пациент, история приёмов, выбранный приём и основные блоки видимы;
- кнопки «Добавить приём» и «Скачать Word» остались на странице;
- левая и правая колонки сохранили исходные Bootstrap-классы.

Зачем:
Layer-тест проверяет рендер шаблона на фейковых данных. Browser-тест проверяет,
что страница открывается через настоящее приложение, авторизацию и реальные данные БД.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from playwright.sync_api import sync_playwright


pytestmark = pytest.mark.browser


def _skip_if_browser_tests_disabled() -> None:
    if os.getenv("RUN_BROWSER_TESTS") != "1":
        pytest.skip("Set RUN_BROWSER_TESTS=1 to run browser tests.")


def _ensure_app_is_running() -> None:
    base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        with urlopen(base_url, timeout=2):
            return
    except URLError:
        pytest.skip(f"FastAPI app is not available at {base_url}.")


@contextmanager
def _browser_page():
    _skip_if_browser_tests_disabled()
    _ensure_app_is_running()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            yield page
        finally:
            browser.close()


def _goto_with_optional_login(page, path: str) -> None:
    base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    target_url = base_url + path
    page.goto(target_url, wait_until="domcontentloaded")

    if "/login" not in page.url:
        return

    login = os.getenv("E2E_LOGIN")
    password = os.getenv("E2E_PASSWORD")
    if not login or not password:
        pytest.skip("Page requires login. Set E2E_LOGIN and E2E_PASSWORD.")

    page.locator('input[name="login"], #login').first.fill(login)
    page.locator('input[name="password"], #password').first.fill(password)
    page.locator('button[type="submit"], input[type="submit"]').first.click()
    page.wait_for_load_state("domcontentloaded")

    if "/login" in page.url:
        pytest.fail("Login failed. Check E2E_LOGIN/E2E_PASSWORD.")

    page.goto(target_url, wait_until="domcontentloaded")


def test_patient_card_preserves_visible_layout_in_browser():
    patient_id = os.getenv("E2E_EXISTING_PATIENT_ID")
    appointment_id = os.getenv("E2E_EXISTING_APPOINTMENT_ID")
    if not patient_id:
        pytest.skip("Set E2E_EXISTING_PATIENT_ID to test patient card.")

    path = f"/patient/{patient_id}"
    if appointment_id:
        path += f"?appointment_id={appointment_id}"

    with _browser_page() as page:
        _goto_with_optional_login(page, path)

        assert page.locator("h2.text-center").count() > 0
        assert page.locator(".col-md-3 #appointmentsList").count() > 0
        assert page.locator(".col-md-3 .btn.btn-success").count() > 0
        assert page.locator(".col-md-9 .card .card-header.bg-secondary").count() > 0
        assert page.locator("#printContent").count() > 0

        page_text = page.locator("body").inner_text()
        assert "История приёмов" in page_text
        assert "Добавить приём" in page_text
        assert "Опрос" in page_text
        assert "Осмотр" in page_text
        assert "Общий анализ крови" in page_text
        assert "Биохимический анализ крови" in page_text
        assert "Расчётные показатели" in page_text
        assert "Общий анализ мочи" in page_text
        assert "Назначения" in page_text
        assert "Скачать Word" in page_text
