# Этап 3: .env.example, .gitignore и app/settings.py

## Куда положить файлы

```text
mis_for_registrations/
  .env.example      ← в корень проекта
  .gitignore        ← в корень проекта

  app/
    settings.py     ← внутрь app/
```

## Нужно ли удалять .env

Нет. Локальный `.env` удалять не нужно, если приложение с ним работает.

Но `.env` нельзя отправлять в Git, архивы и другим людям, потому что внутри пароль от БД.

Правильная схема:

```text
.env           — настоящий локальный файл с паролем, остается только на твоем компьютере
.env.example   — шаблон без настоящего пароля, хранится в проекте
.gitignore     — запрещает случайно добавить .env в Git
```

## Что должно быть в .env

Скопируй `.env.example` в `.env` и замени пароль:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mis_for_registrations
DB_USER=postgres
DB_PASSWORD=твой_пароль

DB_POOL_MIN_CONN=1
DB_POOL_MAX_CONN=10

SESSION_SECRET_KEY=dev-local-secret
```

## Проверка

После добавления файлов приложение должно запускаться так:

```cmd
uvicorn app.main:app --reload
```

Если приложение падает с ошибкой про `DB_PORT`, `DB_NAME`, `DB_PASSWORD` или `SESSION_SECRET_KEY`, значит `.env` лежит не в корне проекта или в нем не хватает переменной.
