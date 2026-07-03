"""baseline schema with MKB dictionary

Revision ID: 0001_baseline_schema
Revises:
Create Date: 2026-07-02
"""

from pathlib import Path
from alembic import op

revision = "0001_baseline_schema"
down_revision = None
branch_labels = None
depends_on = None


SQL_FILES = [
    "01 создание таблиц.sql",
    "02 настройка связей ключей и ограничений.sql",
    "03 создание и заполнение таблиц МКБ.sql",
]


def _read_sql(filename: str) -> str:
    project_root = Path(__file__).resolve().parents[2]
    path = project_root / "database" / filename
    return path.read_text(encoding="utf-8")


def _execute_sql_file(filename: str) -> None:
    # exec_driver_sql отправляет SQL напрямую в драйвер psycopg2.
    # Так надежнее выполнять большие .sql-файлы с несколькими SQL-командами.
    connection = op.get_bind()
    connection.exec_driver_sql(_read_sql(filename))


def upgrade() -> None:
    # Тестовые данные сюда намеренно не входят.
    # Baseline = структура БД + справочник МКБ, пригодные для production/dev.
    for filename in SQL_FILES:
        _execute_sql_file(filename)


def downgrade() -> None:
    # Baseline-миграция предназначена для чистой установки.
    # Автоматический downgrade не задаем, чтобы случайно не удалить медицинские данные.
    pass
