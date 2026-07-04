# Этап 2: вынос SQL из сервисов в repositories

Назначение архива: продолжение предыдущего дробления `patients.py`.

На прошлом этапе логика была разделена на роутеры и сервисы. На этом этапе SQL-запросы, которые всё ещё жили в сервисах, вынесены в папку:

```text
app/repositories/
```

## Что добавляется

```text
app/repositories/
  __init__.py
  patients.py
  appointments.py
  surveys.py
  examinations.py
  labs.py
  diagnoses.py
  prescriptions.py
```

## Какие сервисы заменить

```text
app/services/patient_appointment_service.py
app/services/appointment_save_service.py
app/services/appointment_diagnosis_service.py
```

Роутеры менять не нужно, если ты уже применила первый архив и всё открывается.

## Логика разделения

### repositories

`repositories` — это тонкий слой SQL.

Правило:

```text
repository получает cursor
repository выполняет SELECT/INSERT
repository возвращает id/row/None или ничего
repository не делает commit/rollback
repository не знает про FastAPI request, HTML, форму и redirect
```

### services

`services` теперь отвечают за бизнес-логику:

```text
разобрать форму
проверить данные
понять, какие строки анализов заполнены
посчитать медицинские показатели
вызвать нужные repository-функции
управлять транзакцией
```

## Что куда вынесено

### app/repositories/patients.py

```text
create_patient
get_patient_for_appointment
```

### app/repositories/appointments.py

```text
create_appointment
```

### app/repositories/surveys.py

```text
insert_survey
```

### app/repositories/examinations.py

```text
insert_examination
```

### app/repositories/labs.py

```text
insert_cbc_result
insert_biochemistry_result
insert_calculated_metric
insert_urinalysis_result
insert_albuminuria_result
insert_ultrasound_result
```

### app/repositories/diagnoses.py

```text
insert_text_diagnoses
find_active_icd10_diagnosis_id
insert_appointment_icd10_diagnosis_row
```

### app/repositories/prescriptions.py

```text
insert_diet_and_recommendations
insert_prescription
```

## Что проверить после копирования

Минимально:

```cmd
pytest
```

Потом глазами открыть:

```text
1. Главная страница
2. Форма нового пациента
3. Форма нового приёма
4. Карточка пациента
```

Если хочешь быстро проверить сохранение без полного ручного чек-листа:

```text
1. Создай пациента с ростом, весом и креатинином
2. Проверь, что открылась карточка
3. Создай повторный приём с изменённым весом и креатинином
4. Проверь, что карточка открылась и новый приём появился
```

## Коммит после проверки

```cmd
git add app/repositories app/services/patient_appointment_service.py app/services/appointment_save_service.py app/services/appointment_diagnosis_service.py
git commit -m "extract appointment repositories"
git push
```

## Важное ограничение

Этот архив не меняет структуру БД и не добавляет миграции.
Он только переносит SQL из сервисов в `repositories`.
