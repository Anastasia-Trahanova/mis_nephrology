from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

from urllib.parse import quote_plus


# Корень проекта:
# app/settings.py -> app/ -> корень проекта
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Загружаем локальный .env из корня проекта.
# Если файла нет, приложение все равно попробует читать переменные окружения ОС.
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


@dataclass(frozen=True)
class Settings:
    # PostgreSQL
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    # Пул подключений
    db_pool_min_conn: int
    db_pool_max_conn: int

    # Сессии
    session_secret_key: str

    @property
    def psycopg2_dsn(self) -> str:
        """
        DSN-строка для psycopg2.

        Пароль не хранится в коде, а приходит из .env или переменных окружения.
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
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)

        return (
            f"postgresql+psycopg2://{user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings(
    db_host=os.getenv("DB_HOST", "localhost").strip(),
    db_port=_int_env("DB_PORT", 5432),
    db_name=_required_env("DB_NAME"),
    db_user=_required_env("DB_USER"),
    db_password=_required_env("DB_PASSWORD"),
    db_pool_min_conn=_int_env("DB_POOL_MIN_CONN", 1),
    db_pool_max_conn=_int_env("DB_POOL_MAX_CONN", 10),
    session_secret_key=_required_env("SESSION_SECRET_KEY"),
)
