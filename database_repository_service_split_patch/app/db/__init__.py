"""
Назначение пакета app.db.

Этот пакет содержит технический слой подключения к PostgreSQL.
Здесь не должно быть SQL по пациентам, приёмам, анализам и шаблонам.

Что редактировать здесь:
- настройки пула подключений;
- способ получения соединения с БД;
- техническую обёртку around psycopg2 connection.

Что не редактировать здесь:
- медицинские расчёты;
- SQL-запросы к таблицам пациентов/приёмов/анализов;
- сборку контекстов HTML-страниц.
"""

from .connection import (
    DATABASE_URL,
    DB_POOL_MAX_CONN,
    DB_POOL_MIN_CONN,
    PooledConnection,
    get_db_connection,
)

__all__ = [
    "DATABASE_URL",
    "DB_POOL_MAX_CONN",
    "DB_POOL_MIN_CONN",
    "PooledConnection",
    "get_db_connection",
]
