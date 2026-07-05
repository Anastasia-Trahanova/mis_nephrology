# Layout-preserving разбиение карточки пациента

Назначение патча: разнести `app/templates/patient_card.html` на partial-шаблоны, **не меняя дизайн, расположение блоков и кнопок**.

## Что важно

Этот патч не должен менять внешний вид страницы. Он сохраняет исходную структуру:

```text
ФИО пациента сверху
левая колонка col-md-3 — история приёмов
кнопка «➕ Добавить приём» — внизу левой панели
правая колонка col-md-9 — выбранный приём
card-header bg-secondary — заголовок приёма
card-body id="printContent" — содержимое приёма
кнопка «Скачать Word» — в card-footer снизу карточки приёма
```

## Какие файлы заменить

```text
app/templates/patient_card.html
app/templates/patient_card/*.html
```

Если у тебя остались файлы от предыдущего неудачного патча, можно просто заменить всю папку:

```cmd
rmdir /s /q app\templates\patient_card
```

потом распаковать этот архив в корень проекта.

## Тесты

Добавлены:

```text
tests/layer/test_patient_card_layout_preserving.py
tests/browser/test_patient_card_layout_preserving.py
```

Layer-тест проверяет:

```text
partial-файлы подключены;
у partial-файлов есть описание назначения;
сохранились ключевые маркеры исходного layout;
шаблон рендерится на фейковых данных;
видны основные медицинские блоки.
```

Browser-тест проверяет реальную страницу через приложение:

```text
ФИО сверху;
левая колонка истории приёмов;
кнопка добавления приёма слева;
правая карточка выбранного приёма;
printContent;
медицинские блоки;
кнопка Word-экспорта снизу.
```

## Запуск

```cmd
pytest tests/layer/test_patient_card_layout_preserving.py
```

При поднятом сервере:

```cmd
set RUN_BROWSER_TESTS=1
set APP_BASE_URL=http://127.0.0.1:8000
set E2E_LOGIN=admin
set E2E_PASSWORD=admin123
set E2E_EXISTING_PATIENT_ID=1
set E2E_EXISTING_APPOINTMENT_ID=1
pytest -rs tests/browser/test_patient_card_layout_preserving.py
```

Подставь свои реальные логин, пароль, patient_id и appointment_id.

## Что не делается

```text
не меняется Python-логика;
не меняются роуты;
не меняется БД;
не меняется порядок медицинских блоков;
не переносится кнопка добавления приёма;
не переносится кнопка Word-экспорта;
не меняются основные Bootstrap-классы layout.
```

## Коммит после проверки

```cmd
git add app/templates/patient_card.html app/templates/patient_card tests/layer/test_patient_card_layout_preserving.py tests/browser/test_patient_card_layout_preserving.py
git commit -m "split patient card template preserving layout"
git push
```
