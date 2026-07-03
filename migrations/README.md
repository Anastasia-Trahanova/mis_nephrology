# Миграции БД

Запуск:

```bash
alembic upgrade head
```

Строка подключения берется из `DATABASE_URL` или из переменных `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`.
