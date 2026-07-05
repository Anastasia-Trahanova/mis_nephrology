# Stage 2: прямые импорты из новых database-модулей

Этот файл описывает не архив как одноразовый патч, а смысл второго этапа
архитектурного разделения database-слоя.

## Что меняется

После первого этапа функции уже лежат в новых местах:

- `app/db/connection.py` — подключение к PostgreSQL;
- `app/repositories/reference_data.py` — справочники;
- `app/repositories/patients.py` — пациенты;
- `app/repositories/appointments.py` — приёмы;
- `app/repositories/lab_history.py` — истории анализов;
- `app/repositories/ckd_prognosis.py` — прогноз ХБП;
- `app/services/patient_card_context_service.py` — context карточки пациента;
- `app/services/appointment_form_context_service.py` — context форм.

На втором этапе роуты и сервисы перестают импортировать всё через
`app.database` и начинают использовать эти модули напрямую.

## Что остаётся

`app/database.py` не удаляется. Он остаётся фасадом совместимости, чтобы старые
импорты и отдельные тесты не сломались сразу.

## Как применить

Из корня проекта:

```cmd
python scripts\apply_database_stage2_direct_imports.py
```

Потом проверить:

```cmd
pytest tests/layer/test_database_stage2_direct_imports.py
pytest tests/layer
```

## Что не затрагивается

- схема БД;
- миграции;
- инструкции по запуску БД;
- SQL-запросы;
- медицинская логика;
- шаблоны;
- CSS/JS.
