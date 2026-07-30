"""
Единая точка чтения и проверки настроек приложения.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(
            f"Не задана переменная окружения {name}. "
            "Проверьте файл .env в корне проекта или переменные окружения."
        )
    return value.strip()


def _int_env(name: str, default: int) -> int:
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


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    values = tuple(
        item.strip().lower()
        for item in os.getenv(name, default).split(",")
        if item.strip()
    )
    if not values:
        raise RuntimeError(f"Переменная окружения {name} не должна быть пустой")
    return values


@dataclass(frozen=True)
class Settings:
    app_env: str

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    db_pool_min_conn: int
    db_pool_max_conn: int

    allowed_hosts: tuple[str, ...]

    session_secret_key: str
    session_cookie_name: str
    session_cookie_max_age_seconds: int
    session_idle_timeout_seconds: int
    session_keepalive_interval_seconds: int
    session_https_only: bool

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def psycopg2_dsn(self) -> str:
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
    app_env=os.getenv("APP_ENV", "dev").strip().lower(),
    db_host=os.getenv("DB_HOST", "localhost").strip(),
    db_port=_int_env("DB_PORT", 5432),
    db_name=_required_env("DB_NAME"),
    db_user=_required_env("DB_USER"),
    db_password=_required_env("DB_PASSWORD"),
    db_pool_min_conn=_int_env("DB_POOL_MIN_CONN", 1),
    db_pool_max_conn=_int_env("DB_POOL_MAX_CONN", 10),
    allowed_hosts=_csv_env(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1,testserver",
    ),
    session_secret_key=_required_env("SESSION_SECRET_KEY"),
    session_cookie_name=os.getenv(
        "SESSION_COOKIE_NAME", "mis_nephrology_session"
    ).strip(),
    session_cookie_max_age_seconds=_int_env(
        "SESSION_COOKIE_MAX_AGE_SECONDS", 604800
    ),
    session_idle_timeout_seconds=_int_env("SESSION_IDLE_TIMEOUT_SECONDS", 3600),
    session_keepalive_interval_seconds=_int_env(
        "SESSION_KEEPALIVE_INTERVAL_SECONDS", 180
    ),
    session_https_only=_bool_env("SESSION_HTTPS_ONLY", False),
)


if settings.is_production and "*" in settings.allowed_hosts:
    raise RuntimeError("В production запрещено использовать ALLOWED_HOSTS=*")
