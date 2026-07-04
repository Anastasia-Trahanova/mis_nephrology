# Тестовый пакет для слоя patients/services/repositories

Этот архив добавляет тесты после двух этапов рефакторинга:

1. большой `app/routers/patients.py` был разделён на роутеры и сервисы;
2. SQL был вынесен из сервисов в `app/repositories/*.py`.

## Что копировать

Скопируй в проект:

```text
tests/layer/
tests/integration/test_patient_appointment_database_workflow.py
tests/browser/test_appointment_form_live_calculations.py
scripts/run_layer_tests.cmd
scripts/run_db_layer_tests.cmd
scripts/run_browser_tests.cmd
```

Linux/macOS-скрипты тоже можно скопировать, если нужны:

```text
scripts/run_layer_tests.sh
scripts/run_db_layer_tests.sh
scripts/run_browser_tests.sh
```

## 1. Быстрая проверка после рефакторинга

```cmd
pytest tests/layer
```

или:

```cmd
scripts\run_layer_tests.cmd
```

Эти тесты безопасные:

- не пишут в БД;
- не требуют запущенного сервера;
- проверяют сервисы, repositories, роутеры и разбор формы через fake-объекты.

## 2. Проверка записи в реальную dev/test БД

```cmd
set RUN_DB_LAYER_TESTS=1
pytest tests/integration/test_patient_appointment_database_workflow.py
```

Этот тест создаёт пациента с фамилией `AUTO_TEST_...`, создаёт первый приём,
проверяет строки в связанных таблицах и затем пытается удалить созданные данные.
Запускать только на dev/test базе.

## 3. Проверка live-расчётов формы в браузере

Установить Playwright:

```cmd
pip install playwright
python -m playwright install chromium
```

Запуск:

```cmd
set RUN_BROWSER_TESTS=1
set APP_BASE_URL=http://127.0.0.1:8000
pytest tests/browser
```

Если есть авторизация:

```cmd
set E2E_LOGIN=...
set E2E_PASSWORD=...
```

Для проверки формы повторного приёма:

```cmd
set E2E_EXISTING_PATIENT_ID=1
```

Для проверки карточки и экспорта:

```cmd
set E2E_EXISTING_PATIENT_ID=1
set E2E_EXISTING_APPOINTMENT_ID=1
```

## Какие тесты что проверяют

```text
tests/layer/test_form_parsing.py
```
Проверяет технический разбор формы: пустые значения, числа с запятой, списки,
индексы колонок анализов, даты.

```text
tests/layer/test_appointment_text_builder.py
```
Проверяет чекбоксы и текстовые блоки осмотра: кожа и отёки.

```text
tests/layer/test_appointment_form_parser.py
```
Проверяет, что HTML-поля формы собираются в структурированный словарь приёма:
опрос, осмотр, анализы, альбуминурия, УЗИ, диагнозы, лекарства, BMI.

```text
tests/layer/test_appointment_save_service.py
```
Проверяет, что `appointment_save_service.py` вызывает нужные repository-функции,
пропускает пустые строки анализов, сохраняет расчётные метрики и альбуминурию.

```text
tests/layer/test_appointment_diagnosis_service.py
```
Проверяет разбор и сохранение МКБ-10 диагнозов.

```text
tests/layer/test_patient_appointment_service_transaction.py
```
Проверяет транзакции создания пациента/приёма: commit при успехе, rollback при ошибке.

```text
tests/layer/test_repository_sql_contracts.py
```
Проверяет SQL-контракты repositories через fake cursor.

```text
tests/layer/test_routers_after_split.py
```
Проверяет новые тонкие роутеры и API фильтрации без запуска сервера.

```text
tests/integration/test_patient_appointment_database_workflow.py
```
Опционально пишет в реальную dev/test БД и проверяет сохранение связанных таблиц.

```text
tests/browser/test_appointment_form_live_calculations.py
```
Опционально открывает приложение в браузере и проверяет live-расчёты BMI,
альбуминурии/ACR, СКФ, API фильтров, карточку и экспорт.

## Рекомендуемый порядок запуска

После копирования тестов:

```cmd
pytest tests/layer
```

Если зелёное — запусти приложение и проверь браузерные тесты:

```cmd
set RUN_BROWSER_TESTS=1
set APP_BASE_URL=http://127.0.0.1:8000
pytest tests/browser
```

Перед коммитом можно дополнительно проверить реальную БД:

```cmd
set RUN_DB_LAYER_TESTS=1
pytest tests/integration/test_patient_appointment_database_workflow.py
```
