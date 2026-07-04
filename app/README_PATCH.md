# patients.py refactor patch

Этот архив — переходная декомпозиция `app/routers/patients.py` на роутеры и сервисы.

## Что внутри

```text
app/
  routers/
    patients.py
    appointment_filters.py
    appointments.py

  services/
    __init__.py
    form_parsing.py
    appointment_form_parser.py
    appointment_text_builder.py
    appointment_save_service.py
    appointment_diagnosis_service.py
    patient_appointment_service.py
```

## Назначение файлов

### `app/routers/patients.py`
Тонкий роутер создания нового пациента и первого приёма.

Оставлен маршрут:

```text
POST /api/patients/new 
```

### `app/routers/appointments.py`
Тонкий роутер создания повторного приёма существующего пациента.

Оставлен маршрут:

```text
POST /api/patients/{patient_id}/appointments/new
```

### `app/routers/appointment_filters.py`
GET API для фильтров главной страницы:

```text
GET /api/appointments/filtered
GET /api/branches
GET /api/locations
GET /api/doctors
GET /api/doctor-locations/{doctor_id}
```

### `app/services/form_parsing.py`
Технический разбор значений формы: пустые строки, числа с запятой, списки значений, безопасный доступ по индексу, даты.

### `app/services/appointment_text_builder.py`
Сборка текстовых описаний для осмотра: кожные покровы и отёки.

### `app/services/appointment_diagnosis_service.py`
Сохранение структурированных диагнозов МКБ-10.

### `app/services/appointment_form_parser.py`
Разбор формы приёма в структурированный словарь: опрос, осмотр, ОАК, биохимия, ОАМ, альбуминурия, УЗИ, диагнозы, диета, назначения.

### `app/services/appointment_save_service.py`
Сохранение всех разделов приёма в БД. SQL пока находится здесь. Следующий этап — вынос SQL в `app/repositories/`.

### `app/services/patient_appointment_service.py`
Транзакционные сценарии: создать нового пациента с первым приёмом и создать повторный приём существующему пациенту.

## Как применить

Перед применением лучше сделать отдельную ветку:

```cmd
git status
git checkout -b refactor-patients-services
```

Скопировать папку `app` из архива поверх своей папки `app`.

## Обязательно поправить `app/main.py`

Найти:

```python
from .routers import pages, patients, auth, ckd_registry
```

Заменить на:

```python
from .routers import pages, patients, appointments, appointment_filters, auth, ckd_registry
```

Найти:

```python
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(patients.router)
app.include_router(ckd_registry.router)
```

Заменить на:

```python
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(appointment_filters.router)
app.include_router(patients.router)
app.include_router(appointments.router)
app.include_router(ckd_registry.router)
```

## Важно про BMI

В `appointment_form_parser.py` используется:

```python
from ..calculations import calculate_bmi
```

Если у тебя `calculate_bmi` ещё не переэкспортирован из `app/calculations.py`, файл попробует fallback:

```python
from ..medical_algorithms.bmi import calculate_bmi
```

То есть файл `app/medical_algorithms/bmi.py` должен уже существовать.

## Что проверить после копирования

```cmd
pytest
```

Потом руками:

1. Открывается главная страница.
2. Работают фильтры филиал / врач / отделение.
3. Открывается форма нового пациента.
4. Создаётся новый пациент.
5. Сохраняются опрос и осмотр.
6. Сохраняются ОАК, биохимия, ОАМ, альбуминурия, УЗИ.
7. Считаются eGFR, Cockcroft-Gault, стадия ХБП.
8. Сохраняются МКБ-10 диагнозы.
9. Сохраняются лекарства.
10. Открывается форма нового приёма старому пациенту.
11. Создаётся повторный приём.
12. Открывается карточка пациента.
13. Работает Word-экспорт.

## Если что-то упало

Проверь в первую очередь:

1. Подключены ли `appointments.router` и `appointment_filters.router` в `main.py`.
2. Существует ли `app/services/__init__.py`.
3. Есть ли `calculate_bmi` в `app/calculations.py` или `app/medical_algorithms/bmi.py`.
4. Не потерялся ли старый URL формы повторного приёма:

```text
/api/patients/{patient_id}/appointments/new
```

## Что дальше

Если после этого всё работает, следующий этап:

```text
app/repositories/
  patients.py
  appointments.py
  surveys.py
  examinations.py
  labs.py
  diagnoses.py
  prescriptions.py
```

Туда постепенно уносим SQL из:

```text
appointment_save_service.py
patient_appointment_service.py
appointment_diagnosis_service.py
```
