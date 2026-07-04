@echo off
REM Браузерные тесты live-расчётов и API фильтров.
REM Перед первым запуском:
REM   pip install playwright
REM   python -m playwright install chromium
REM
REM Можно переопределить:
REM   set APP_BASE_URL=http://127.0.0.1:8000
REM   set E2E_LOGIN=...
REM   set E2E_PASSWORD=...
REM   set E2E_EXISTING_PATIENT_ID=1
REM   set E2E_EXISTING_APPOINTMENT_ID=1

if "%APP_BASE_URL%"=="" set APP_BASE_URL=http://127.0.0.1:8000
set RUN_BROWSER_TESTS=1
pytest tests\browser
