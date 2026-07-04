# Патч нормализации и валидации клинических полей

## Что добавлено

Добавлен слой нормализации клинических числовых значений перед валидацией, парсингом и сохранением:

```text
app/services/clinical_value_normalization.py
```

И заменяются файлы:

```text
app/services/patient_appointment_service.py
app/services/appointment_form_parser.py
app/validation.py
tests/layer/test_clinical_value_normalization.py
tests/layer/test_appointment_form_parser.py
tests/integration/test_patient_appointment_database_workflow.py
pytest.ini
```

## Зачем

Врач может вводить часть значений в привычном альтернативном формате. Например удельный вес мочи:

```text
1015
```

а внутренний формат хранения и валидации у проекта:

```text
1.015
```

Раньше такой ввод блокировался ошибкой валидации. Теперь он нормализуется до `1.015`, проходит валидацию и сохраняется в БД в едином формате.

## Что нормализуется сейчас

### Общие числовые поля

Для всех основных числовых полей формы:

```text
5,1 -> 5.1
1 234,5 -> 1234.5
"" -> None
```

При этом единицы не пересчитываются.

### Удельный вес мочи

Безопасные варианты:

```text
1015  -> 1.015
1005  -> 1.005
1030  -> 1.030
1,015 -> 1.015
1.015 -> 1.015
```

Не нормализуются:

```text
900
1500
1.5
```

Они должны быть пойманы медицинской валидацией как ошибочные значения.

### Гематокрит

Безопасные варианты:

```text
0.39 -> 39
0,39 -> 39
39   -> 39
```

Не нормализуется:

```text
1.2
```

Потому что автоматическое превращение `1.2` в `120` было бы опасной догадкой.

## Что принципиально НЕ делаем

Не делим и не умножаем значения без однозначного правила.

Например:

```text
креатинин 100 не трогаем
глюкозу 55 не делим на 10
тромбоциты 250 не трогаем
ферритин 1200 не трогаем
```

Если значение выходит за широкий технический диапазон, его должна остановить валидация, а не скрытая нормализация.

## Как применить

Скопировать папки из архива в корень проекта с заменой файлов.

Потом запустить:

```cmd
pytest tests/layer
```

Дальше опционально:

```cmd
set RUN_DB_LAYER_TESTS=1
pytest tests/integration/test_patient_appointment_database_workflow.py
```

## Ожидаемый результат

Layer-тесты должны пройти полностью.

Интеграционный тест должен создать пациента, принять `specific_gravity = 1015`, сохранить в БД `1.015`, проверить сохранение всех разделов и удалить тестового пациента.

## Коммит после проверки

```cmd
git add app/services/clinical_value_normalization.py app/services/patient_appointment_service.py app/services/appointment_form_parser.py app/validation.py tests/layer/test_clinical_value_normalization.py tests/layer/test_appointment_form_parser.py tests/integration/test_patient_appointment_database_workflow.py pytest.ini
git commit -m "normalize clinical form values"
git push
```
