# МИС Нефролога

Веб-приложение для организации амбулаторного приёма нефролога: ведения пациентов, медицинских приёмов, лабораторных и инструментальных исследований, расчёта нефрологических показателей, расписания врачей, регистра ХБП и формирования заключений в Word.

> Проект находится в разработке и не является зарегистрированным медицинским изделием. Результаты расчётов требуют врачебной интерпретации.

## Возможности

- авторизация пользователей и разграничение ролей врача и администратора;
- защищённые сессии с контролем бездействия;
- поиск и регистрация пациентов;
- первичные и повторные приёмы;
- подстановка данных предыдущего приёма без создания дублей диагнозов;
- карточка пациента с историей приёмов;
- жалобы, анамнез, осмотр, диагнозы МКБ-10, назначения и рекомендации;
- динамические таблицы ОАК, биохимии, ОАМ и альбуминурии;
- хранение данных УЗИ и других исследований;
- расчёт ИМТ, CKD-EPI 2021, Cockcroft–Gault, стадии ХБП, ACR и категории альбуминурии A1/A2/A3;
- оценка риска прогрессирования ХБП по KDIGO;
- расписание врачей;
- отметки статуса записи и переход из расписания к пациенту или медицинскому приёму;
- регистр пациентов с ХБП;
- экспорт выбранного приёма в DOCX;
- журнал действий пользователей для администратора;
- горячие клавиши и встроенная справка по ним.

## Технологии

- Python 3.11+
- FastAPI и Starlette
- Jinja2
- PostgreSQL
- psycopg2 / asyncpg
- Alembic
- Bootstrap и собственные CSS/JavaScript-модули
- python-docx
- pytest
- Playwright для браузерных тестов

## Структура

```text
app/
  db/                  подключение к PostgreSQL
  medical_algorithms/  медицинские расчёты
  middleware/          middleware приложения
  repositories/        SQL-запросы и слой доступа к данным
  routers/             HTTP-маршруты FastAPI
  security/            права доступа и безопасность
  services/            бизнес-логика
  static/              CSS и JavaScript
  templates/           Jinja2-шаблоны

database/               SQL-файлы и инструкции по базе
migrations/             Alembic-миграции
scripts/                служебные команды
tests/                  модульные, layer-, интеграционные и browser-тесты
docs/                   актуальные ручные чек-листы
```

## Установка

### 1. Создать виртуальное окружение

Windows CMD:

```bat
python -m venv venv
venv\Scripts\activate
```

### 2. Установить зависимости

```bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Для браузерных тестов дополнительно:

```bat
pip install playwright
python -m playwright install chromium
```

### 3. Настроить окружение

Скопируйте шаблон:

```bat
copy .env.example .env
```

Заполните `.env`:

```env
APP_ENV=dev

DB_HOST=localhost
DB_PORT=5432
DB_NAME=mis_for_registrations
DB_USER=postgres
DB_PASSWORD=change_me

DB_POOL_MIN_CONN=1
DB_POOL_MAX_CONN=10

SESSION_SECRET_KEY=change_me_dev_secret
SESSION_COOKIE_NAME=mis_nephrology_session
SESSION_COOKIE_MAX_AGE_SECONDS=604800
SESSION_IDLE_TIMEOUT_SECONDS=3600
SESSION_KEEPALIVE_INTERVAL_SECONDS=180
SESSION_HTTPS_ONLY=false
```

Файл `.env` содержит секреты и не должен попадать в Git.

## База данных

### Обновить существующую базу

```bat
python -m alembic upgrade head
```

Проверить текущую ревизию:

```bat
python -m alembic current
```

### Создать чистую dev-базу

Команда удаляет существующую базу и предназначена только для разработки:

```bat
python scripts\reset_db.py --yes
```

Без демонстрационных данных:

```bat
python scripts\reset_db.py --yes --no-demo
```

Применить миграции без удаления существующей базы:

```bat
python scripts\reset_db.py --no-drop --no-demo
```

## Пользователи

Создание администратора:

```bat
python scripts\create_admin_user.py --help
```

Сброс пароля пользователя:

```bat
python scripts\reset_user_password.py --help
```

Пароли хранятся в базе только в виде хеша.

## Запуск

```bat
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Откройте:

```text
http://127.0.0.1:8000
```

## Тесты

Основные тесты:

```bat
pytest
```

Быстрые layer-тесты:

```bat
pytest tests\layer
```

Интеграционные тесты с тестовой БД:

```bat
set RUN_DB_LAYER_TESTS=1
pytest tests\integration
```

Browser-тесты при запущенном приложении:

```bat
set RUN_BROWSER_TESTS=1
set APP_BASE_URL=http://127.0.0.1:8000
pytest -rs tests\browser
```

Также доступны готовые команды в папке `scripts/`.

## Важные соглашения

- Стадии ХБП хранятся с русской буквой `С`: `С1`, `С2`, `С3а`, `С3б`, `С4`, `С5`.
- Будущая запись в расписании не должна считаться состоявшимся медицинским приёмом.
- Миграции нельзя удалять после применения к используемым базам.
- В Git нельзя помещать `.env`, дампы БД, журналы, временные архивы и реальные персональные медицинские данные.

## Безопасность

Внутренние страницы доступны только после авторизации. Для production необходимо:

- использовать длинный случайный `SESSION_SECRET_KEY`;
- включить HTTPS;
- установить `SESSION_HTTPS_ONLY=true`;
- создать отдельных пользователей вместо общих учётных записей;
- регулярно выполнять резервное копирование PostgreSQL;
- не использовать демонстрационные данные и пароли.
