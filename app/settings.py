"""
Назначение файла: единая точка чтения настроек приложения.

Как работает:
- загружает переменные из .env в корне проекта;
- проверяет обязательные настройки БД и сессий;
- приводит числовые и boolean-настройки к нормальным Python-типам;
- отдаёт объект settings, который импортируют main.py, подключение к БД и security-слой.

Что редактировать здесь:
- добавлять новые настройки приложения;
- менять значения по умолчанию для локальной разработки;
- добавлять валидацию переменных окружения.

Что не редактировать здесь:
- пароли пользователей МИС;
- медицинскую логику;
- SQL-запросы.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


# Корень проекта: app/settings.py -> app/ -> корень проекта.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Загружаем локальный .env из корня проекта.
# Если файла нет, приложение всё равно попробует читать переменные окружения ОС.
load_dotenv(PROJECT_ROOT / ".env")


def _required_env(name: str) -> str:
    """Возвращает обязательную переменную окружения или падает с понятной ошибкой."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(
            f"Не задана переменная окружения {name}. "
            f"Проверьте файл .env в корне проекта или переменные окружения."
        )
    return value.strip()


def _int_env(name: str, default: int) -> int:
    """Читает целочисленную переменную окружения с понятной ошибкой."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(
            f"Переменная окружения {name} должна быть целым числом, сейчас: {value!r}"
        ) from exc


def _bool_env(name: str, default: bool) -> bool:
    """
    Читает boolean-переменную окружения.

    Допустимые true: 1, true, yes, y, on.
    Допустимые false: 0, false, no, n, off.
    Это нужно для SESSION_HTTPS_ONLY: локально false, на сервере с HTTPS true.
    """
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False

    raise RuntimeError(
        f"Переменная окружения {name} должна быть true/false, сейчас: {value!r}"
    )


@dataclass(frozen=True)
class Settings:
    # Среда запуска.
    # dev — локальная разработка; production — сервер с реальными пользователями.
    app_env: str

    # PostgreSQL.
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    # Пул подключений к БД.
    db_pool_min_conn: int
    db_pool_max_conn: int

    # Сессии FastAPI/Starlette.
    session_secret_key: str
    session_cookie_name: str
    session_cookie_max_age_seconds: int
    session_idle_timeout_seconds: int
    session_keepalive_interval_seconds: int
    session_https_only: bool

    @property
    def is_production(self) -> bool:
        """True, если приложение запущено в production-режиме."""
        return self.app_env.lower() == "production"

    @property
    def psycopg2_dsn(self) -> str:
        """
        DSN-строка для psycopg2.

        Пароль БД не хранится в коде, а приходит из .env или переменных окружения.
        """
        return (
            f"host={self.db_host} "
            f"port={self.db_port} "
            f"dbname={self.db_name} "
            f"user={self.db_user} "
            f"password={self.db_password}"
        )

    @property
    def sqlalchemy_url(self) -> str:
        """SQLAlchemy URL для Alembic и сервисов, которым нужен SQLAlchemy-style DSN."""
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return (
            f"postgresql+psycopg2://{user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings(
    app_env=os.getenv("APP_ENV", "dev").strip().lower(),
    db_host=os.getenv("DB_HOST", "localhost").strip(),
    db_port=_int_env("DB_PORT", 5432),
    db_name=_required_env("DB_NAME"),
    db_user=_required_env("DB_USER"),
    db_password=_required_env("DB_PASSWORD"),
    db_pool_min_conn=_int_env("DB_POOL_MIN_CONN", 1),
    db_pool_max_conn=_int_env("DB_POOL_MAX_CONN", 10),
    session_secret_key=_required_env("SESSION_SECRET_KEY"),
    session_cookie_name=os.getenv(
        "SESSION_COOKIE_NAME", "mis_nephrology_session"
    ).strip(),
    # Cookie может физически жить дольше idle-timeout, но сервер не пустит пользователя,
    # если last_seen_at старше SESSION_IDLE_TIMEOUT_SECONDS.
    session_cookie_max_age_seconds=_int_env("SESSION_COOKIE_MAX_AGE_SECONDS", 604800),
    # 60 минут бездействия по умолчанию.
    session_idle_timeout_seconds=_int_env("SESSION_IDLE_TIMEOUT_SECONDS", 3600),
    # JS будет отправлять keepalive раз в 3 минуты, только если врач реально что-то делал.
    session_keepalive_interval_seconds=_int_env(
        "SESSION_KEEPALIVE_INTERVAL_SECONDS", 180
    ),
    # Локально false, на HTTPS-сервере true.
    session_https_only=_bool_env("SESSION_HTTPS_ONLY", False),
)
