"""
Назначение файла: единая точка подключения к PostgreSQL.

Этот файл выполняет только технические задачи:
- берёт DSN и настройки пула из app.settings;
- лениво создаёт ThreadedConnectionPool;
- выдаёт соединение через get_db_connection();
- делает commit при успешном выходе из with-блока;
- делает rollback при исключении;
- возвращает соединение обратно в пул.

Что редактировать здесь:
- размер пула DB_POOL_MIN_CONN / DB_POOL_MAX_CONN через настройки;
- поведение подключения/rollback/commit;
- тип cursor_factory, если когда-нибудь понадобится другой формат результата.

Что не редактировать здесь:
- SQL-запросы к медицинским таблицам;
- расчёты СКФ/ACR/ХБП;
- сборку данных для шаблонов.
"""

from __future__ import annotations

import threading

from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from app.settings import settings

DATABASE_URL = settings.psycopg2_dsn
DB_POOL_MIN_CONN = settings.db_pool_min_conn
DB_POOL_MAX_CONN = settings.db_pool_max_conn

_pool: ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> ThreadedConnectionPool:
    """Лениво создаёт общий пул подключений к PostgreSQL."""
    global _pool

    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ThreadedConnectionPool(
                    DB_POOL_MIN_CONN,
                    DB_POOL_MAX_CONN,
                    dsn=DATABASE_URL,
                    cursor_factory=RealDictCursor,
                )

    return _pool


class PooledConnection:
    """
    Контекстная обёртка вокруг psycopg2 connection.

    Использование:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(...)

    При успешном выходе выполняется commit.
    При исключении выполняется rollback.
    Физическое соединение не закрывается, а возвращается в пул.
    """

    def __init__(self):
        self.pool = _get_pool()
        self.conn = self.pool.getconn()

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            self.pool.putconn(self.conn)

        return False

    def __getattr__(self, item):
        return getattr(self.conn, item)


def get_db_connection() -> PooledConnection:
    """Возвращает pooled connection wrapper для работы с БД."""
    return PooledConnection()
