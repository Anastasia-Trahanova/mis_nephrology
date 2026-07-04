# Тесты слоя пациентов, приёмов, сервисов и repositories

Этот набор тестов был добавлен после дробления большого `app/routers/patients.py` на:

```text
app/routers/patients.py
app/routers/appointments.py
app/routers/appointment_filters.py
app/services/*.py
app/repositories/*.py
```

Цель тестов — быстро проверять, что после рефакторинга не сломались:

- разбор HTML-формы приёма;
- чекбоксы и текстовые поля осмотра;
- серверный расчёт BMI при парсинге формы;
- сохранение разделов приёма через `appointment_save_service.py`;
- SQL-контракты repository-функций;
- транзакционная логика создания пациента и приёма;
- опционально: реальная запись в БД и чтение сохранённых данных;
- опционально: live-расчёты в браузере.

## Быстрые безопасные тесты

Эти тесты не пишут в БД и не требуют запущенного приложения:

```cmd
pytest tests/layer
```

Они проверяют код модулей напрямую и используют fake form / fake cursor / monkeypatch.

## Опциональный тест реальной БД

Этот тест создаёт тестового пациента в текущей БД, проверяет сохранение связанных данных и затем пытается удалить созданные записи.

Запускать только на dev/test базе:

```cmd
set RUN_DB_LAYER_TESTS=1
pytest tests/integration/test_patient_appointment_database_workflow.py
```

Если используешь PowerShell:

```powershell
$env:RUN_DB_LAYER_TESTS = "1"
pytest tests/integration/test_patient_appointment_database_workflow.py
```

## Опциональные браузерные тесты формы

Эти тесты требуют запущенного приложения и Playwright:

```cmd
pip install playwright pytest-playwright
python -m playwright install chromium
set RUN_BROWSER_TESTS=1
set APP_BASE_URL=http://127.0.0.1:8000
set E2E_LOGIN=admin
set E2E_PASSWORD=admin123
pytest -rs tests/browser
```


Для проверки формы повторного приёма задай ID существующего пациента:

```cmd
set E2E_EXISTING_PATIENT_ID=1
```

## Важное правило

Быстрые тесты из `tests/layer` должны запускаться после каждого рефакторинга. Интеграционные и браузерные — перед большим коммитом или перед передачей врачу.
