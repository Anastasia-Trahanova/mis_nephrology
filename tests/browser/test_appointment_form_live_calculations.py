"""
ОПЦИОНАЛЬНЫЕ браузерные тесты формы приёма.

Что тестируется:
- форма нового пациента открывается в браузере;
- BMI пересчитывается в реальном времени при изменении роста/веса;
- форма повторного приёма открывается и BMI тоже пересчитывается;
- API фильтров отвечает без 500;
- при заданных селекторах можно проверять live-расчёт СКФ и альбуминурии;
- карточка пациента/экспорт можно проверить по уже существующим ID.

Зачем:
unit-тесты не видят JavaScript. Эти тесты нужны, чтобы после правок шаблонов и
_scripts.html быстро поймать поломку live-расчётов и API фильтров.

Как запускать:
    pip install playwright
    python -m playwright install chromium
    set RUN_BROWSER_TESTS=1
    set APP_BASE_URL=http://127.0.0.1:8000
    pytest tests/browser/test_appointment_form_live_calculations.py

Если приложение требует логин:
    set E2E_LOGIN=...
    set E2E_PASSWORD=...

Для формы повторного приёма:
    set E2E_EXISTING_PATIENT_ID=1

Для проверки карточки/экспорта:
    set E2E_EXISTING_PATIENT_ID=1
    set E2E_EXISTING_APPOINTMENT_ID=1

Если у полей СКФ/ACR нестандартные селекторы, можно задать:
    set E2E_EGFR_SELECTOR=input[name="egfr_ckdepi"]
    set E2E_ACR_SELECTOR=input[name="albumin_creatinine_ratio"]
    set E2E_ALBUMINURIA_CATEGORY_SELECTOR=input[name="albuminuria_category"]
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import pytest


pytestmark = pytest.mark.browser


def _skip_if_browser_tests_disabled():
    if os.getenv("RUN_BROWSER_TESTS") != "1":
        pytest.skip("Browser tests are disabled. Set RUN_BROWSER_TESTS=1 to run them.")


def _base_url() -> str:
    return os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@contextmanager
def _browser_page():
    _skip_if_browser_tests_disabled()
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=os.getenv("E2E_HEADLESS", "1") != "0")
        page = browser.new_page()
        try:
            yield page
        finally:
            browser.close()


def _goto_with_optional_login(page, path: str):
    target_url = f"{_base_url()}{path}"
    page.goto(target_url, wait_until="domcontentloaded")

    # Если middleware перекинул на login или на странице есть поле пароля,
    # пробуем авторизоваться тестовыми учётными данными из env.
    password_fields = page.locator('input[type="password"], input[name="password"]')
    if password_fields.count() > 0:
        login = os.getenv("E2E_LOGIN")
        password = os.getenv("E2E_PASSWORD")
        if not login or not password:
            pytest.skip("Page requires login. Set E2E_LOGIN and E2E_PASSWORD.")

        login_selectors = [
            'input[name="login"]',
            'input[name="username"]',
            'input[name="email"]',
            'input[type="text"]',
        ]
        for selector in login_selectors:
            loc = page.locator(selector)
            if loc.count() > 0:
                loc.first.fill(login)
                break

        password_fields.first.fill(password)
        submit = page.locator('button[type="submit"], input[type="submit"]')
        if submit.count() == 0:
            pytest.skip("Login form found, but submit button was not found.")
        submit.first.click()
        page.wait_for_load_state("domcontentloaded")
        page.goto(target_url, wait_until="domcontentloaded")


def _first_existing_locator(page, selectors: list[str]):
    for selector in selectors:
        loc = page.locator(selector)
        if loc.count() > 0:
            return loc.first
    return None


def _fill_first(page, selectors: list[str], value: str) -> None:
    loc = _first_existing_locator(page, selectors)
    if not loc:
        pytest.fail(f"Не найдено поле формы. Проверенные селекторы: {selectors}")
    loc.fill(value)


def _value_first(page, selectors: list[str]) -> str:
    loc = _first_existing_locator(page, selectors)
    if not loc:
        pytest.fail(f"Не найдено поле результата. Проверенные селекторы: {selectors}")
    return loc.input_value()


def _maybe_value_first(page, selectors: list[str]) -> str | None:
    loc = _first_existing_locator(page, selectors)
    if not loc:
        return None
    try:
        return loc.input_value()
    except Exception:
        return loc.text_content()


def _assert_bmi_live_calculation(page):
    _fill_first(page, ['#heightInput', 'input[name="height"]'], "170")
    _fill_first(page, ['#weightInput', 'input[name="weight"]'], "70")
    page.wait_for_timeout(200)

    bmi_value = _value_first(page, ['#bmiInput', 'input[name="bmi"]'])
    assert bmi_value in {"24.22", "24,22"}

    _fill_first(page, ['#weightInput', 'input[name="weight"]'], "75")
    page.wait_for_timeout(200)
    bmi_value = _value_first(page, ['#bmiInput', 'input[name="bmi"]'])
    assert bmi_value in {"25.95", "25,95"}


def test_new_patient_form_recalculates_bmi_in_real_time():
    """Проверяет live-BMI на форме нового пациента."""
    with _browser_page() as page:
        _goto_with_optional_login(page, os.getenv("E2E_NEW_PATIENT_PATH", "/new-patient"))
        _assert_bmi_live_calculation(page)


def test_new_appointment_form_recalculates_bmi_in_real_time_when_patient_id_is_provided():
    """Проверяет live-BMI на форме повторного приёма старого пациента."""
    patient_id = os.getenv("E2E_EXISTING_PATIENT_ID")
    if not patient_id:
        pytest.skip("Set E2E_EXISTING_PATIENT_ID to test the new appointment form.")

    with _browser_page() as page:
        _goto_with_optional_login(page, f"/new-appointment/{patient_id}")
        _assert_bmi_live_calculation(page)


def test_live_albuminuria_calculation_when_selector_is_available():
    """
    Проверяет live-ACR/категорию альбуминурии, если в форме есть доступные поля результата.

    По умолчанию тест ищет распространённые селекторы. Если у тебя другие name/id,
    задай E2E_ACR_SELECTOR и E2E_ALBUMINURIA_CATEGORY_SELECTOR.
    """
    with _browser_page() as page:
        _goto_with_optional_login(page, os.getenv("E2E_NEW_PATIENT_PATH", "/new-patient"))

        _fill_first(page, ['input[name="urine_albumin"]'], "30")
        _fill_first(page, ['input[name="urine_creatinine"]'], "10")

        # Единицы обычно уже выбраны по умолчанию. Если select есть — выставим явно.
        for selector, value in [
            ('select[name="urine_albumin_unit"]', "mg_l"),
            ('select[name="urine_creatinine_unit"]', "mmol_l"),
        ]:
            loc = page.locator(selector)
            if loc.count() > 0:
                loc.first.select_option(value)

        page.wait_for_timeout(300)

        acr_selector = os.getenv("E2E_ACR_SELECTOR")
        category_selector = os.getenv("E2E_ALBUMINURIA_CATEGORY_SELECTOR")

        acr_value = _maybe_value_first(
            page,
            [acr_selector] if acr_selector else [
                'input[name="albumin_creatinine_ratio"]',
                'input[name="acr"]',
                '[data-testid="acr"]',
                '.acr-result',
            ],
        )
        category_value = _maybe_value_first(
            page,
            [category_selector] if category_selector else [
                'input[name="albuminuria_category"]',
                '[data-testid="albuminuria-category"]',
                '.albuminuria-category',
            ],
        )

        if acr_value is None and os.getenv("E2E_REQUIRE_LIVE_ACR") != "1":
            pytest.skip("ACR result selector was not found. Set E2E_ACR_SELECTOR or E2E_REQUIRE_LIVE_ACR=1.")

        assert acr_value not in {None, "", "—"}
        if category_value is not None:
            assert category_value.strip() in {"A1", "A2", "A3"}


def test_live_egfr_calculation_when_selector_is_available():
    """
    Проверяет live-СКФ, если в форме есть доступное поле результата.

    Если поле результата называется иначе, задай E2E_EGFR_SELECTOR.
    """
    with _browser_page() as page:
        _goto_with_optional_login(page, os.getenv("E2E_NEW_PATIENT_PATH", "/new-patient"))

        # Для live-расчёта СКФ обычно нужны дата рождения, пол, вес и креатинин.
        birth = page.locator('input[name="birth_date"]')
        if birth.count() > 0:
            birth.first.fill("1980-01-15")

        _fill_first(page, ['#weightInput', 'input[name="weight"]'], "70")
        _fill_first(page, ['input[name="creatinine"]'], "100")
        page.wait_for_timeout(300)

        egfr_selector = os.getenv("E2E_EGFR_SELECTOR")
        egfr_value = _maybe_value_first(
            page,
            [egfr_selector] if egfr_selector else [
                'input[name="egfr_ckdepi"]',
                'input[name="egfr"]',
                '[data-testid="egfr"]',
                '.egfr-result',
            ],
        )

        if egfr_value is None and os.getenv("E2E_REQUIRE_LIVE_EGFR") != "1":
            pytest.skip("eGFR result selector was not found. Set E2E_EGFR_SELECTOR or E2E_REQUIRE_LIVE_EGFR=1.")

        assert egfr_value not in {None, "", "—"}


def test_filter_api_endpoints_do_not_return_server_error():
    """Проверяет, что API фильтров после выноса роутера отвечает без 500."""
    with _browser_page() as page:
        _goto_with_optional_login(page, "/")
        for path in ["/api/branches", "/api/appointments/filtered?limit=5"]:
            response = page.request.get(f"{_base_url()}{path}")
            assert response.status < 500, f"{path} returned {response.status}"


def test_patient_card_and_docx_export_open_when_ids_are_provided():
    """Проверяет, что карточка пациента и DOCX-экспорт не падают, если заданы ID."""
    patient_id = os.getenv("E2E_EXISTING_PATIENT_ID")
    appointment_id = os.getenv("E2E_EXISTING_APPOINTMENT_ID")
    if not patient_id or not appointment_id:
        pytest.skip("Set E2E_EXISTING_PATIENT_ID and E2E_EXISTING_APPOINTMENT_ID to test card/export.")

    with _browser_page() as page:
        _goto_with_optional_login(page, f"/patient/{patient_id}?appointment_id={appointment_id}")
        assert page.locator("body").text_content()

        response = page.request.get(f"{_base_url()}/export/{appointment_id}/docx")
        # 200 — экспорт есть; 404/405 может означать другой URL экспорта в локальной версии.
        assert response.status < 500
