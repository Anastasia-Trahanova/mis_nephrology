"""
Что тестируется:
- открытие карточки пациента в реальном браузере через Playwright;
- рендер ключевых блоков карточки после разделения patient_card.html на partials;
- наличие ссылки на добавление приёма;
- наличие ссылки на Word-экспорт для выбранного приёма.

Как тестируется:
Тест требует уже запущенное FastAPI-приложение и реальные id пациента/приёма.
Он не создаёт данные и не пишет в БД. Это проверка отображения существующей
карточки через настоящий браузер.

Зачем:
Layer-тесты проверяют Jinja-рендер на фейковых данных. Browser-тест проверяет,
что реальная страница приложения открывается после авторизации и содержит
ожидаемые блоки.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from urllib.error import URLError
from urllib.request import urlopen

import pytest

pytestmark = pytest.mark.browser


def _browser_tests_enabled() -> bool:
    return os.getenv("RUN_BROWSER_TESTS") == "1"


def _base_url() -> str:
    return os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _ensure_app_is_running() -> None:
    try:
        with urlopen(_base_url(), timeout=2):
            return
    except URLError:
        pytest.skip(
            f"FastAPI app is not available at {_base_url()}. "
            "Start it first with: python -m uvicorn app.main:app --reload"
        )


@contextmanager
def _browser_page():
    if not _browser_tests_enabled():
        pytest.skip("Set RUN_BROWSER_TESTS=1 to run browser tests.")

    _ensure_app_is_running()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("Playwright is not installed. Install it with: pip install playwright")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            yield page
        finally:
            browser.close()


def _goto_with_optional_login(page, path: str) -> None:
    target_url = _base_url() + path
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
        pytest.fail("Не удалось авторизоваться. Проверь E2E_LOGIN/E2E_PASSWORD.")

    if path not in page.url:
        page.goto(target_url, wait_until="domcontentloaded")


def test_patient_card_page_renders_main_sections_in_browser():
    """
    Проверяет, что реальная карточка пациента открывается и содержит основные блоки.

    Требует:
    - RUN_BROWSER_TESTS=1
    - APP_BASE_URL=http://127.0.0.1:8000
    - E2E_LOGIN/E2E_PASSWORD, если включена авторизация
    - E2E_EXISTING_PATIENT_ID
    - опционально E2E_EXISTING_APPOINTMENT_ID
    """
    patient_id = os.getenv("E2E_EXISTING_PATIENT_ID")
    if not patient_id:
        pytest.skip("Set E2E_EXISTING_PATIENT_ID to test patient card rendering.")

    appointment_id = os.getenv("E2E_EXISTING_APPOINTMENT_ID")
    path = f"/patient/{patient_id}"
    if appointment_id:
        path += f"?appointment_id={appointment_id}"

    with _browser_page() as page:
        _goto_with_optional_login(page, path)

        assert page.locator('[data-testid="patient-card-page"]').count() > 0
        assert page.locator('[data-testid="patient-card-header"]').count() > 0
        assert page.locator('[data-testid="appointments-sidebar"]').count() > 0
        assert page.locator('[data-testid="add-appointment-link"]').count() > 0

        if appointment_id:
            for selector in [
                '[data-testid="visit-summary-section"]',
                '[data-testid="survey-section"]',
                '[data-testid="examination-section"]',
                '[data-testid="urinalysis-history-section"]',
                '[data-testid="diagnoses-section"]',
                '[data-testid="prescriptions-section"]',
                '[data-testid="docx-export-link"]',
            ]:
                assert page.locator(selector).count() > 0, f"Не найден блок {selector}"


def test_patient_card_export_link_has_expected_url_when_appointment_is_selected():
    """Проверяет наличие корректной ссылки Word-экспорта на карточке пациента."""
    patient_id = os.getenv("E2E_EXISTING_PATIENT_ID")
    appointment_id = os.getenv("E2E_EXISTING_APPOINTMENT_ID")

    if not patient_id or not appointment_id:
        pytest.skip("Set E2E_EXISTING_PATIENT_ID and E2E_EXISTING_APPOINTMENT_ID to test export link.")

    with _browser_page() as page:
        _goto_with_optional_login(page, f"/patient/{patient_id}?appointment_id={appointment_id}")

        export_link = page.locator('[data-testid="docx-export-link"]').first
        assert export_link.count() > 0

        href = export_link.get_attribute("href")
        assert href == f"/export/{appointment_id}/docx"
