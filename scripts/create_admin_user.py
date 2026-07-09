"""
Назначение файла: создание первого администратора МИС из командной строки.

Как работает:
- запускается разработчиком/администратором вручную;
- спрашивает логин и пароль;
- сохраняет в таблицу users только password_hash;
- открытый пароль не записывает ни в код, ни в .env, ни в БД.

Когда использовать:
- после создания чистой БД;
- если в системе ещё нет администратора;
- для локальной разработки и первичной настройки сервера.

Что редактировать здесь:
- правила валидации логина/пароля;
- поведение при существующем пользователе.

Что не редактировать здесь:
- алгоритм расчёта медицинских данных;
- HTML-страницы;
- миграции БД.
"""

from __future__ import annotations

from getpass import getpass
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.connection import get_db_connection  # noqa: E402
from app.routers.auth import make_password_hash  # noqa: E402


def ask_non_empty(prompt: str) -> str:
    """Запрашивает непустое значение в терминале."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Значение не должно быть пустым.")


def ask_password_twice() -> str:
    """Запрашивает пароль два раза, чтобы избежать опечатки."""
    while True:
        password = getpass("Пароль администратора: ")
        password_repeat = getpass("Повторите пароль: ")

        if not password:
            print("Пароль не должен быть пустым.")
            continue
        if len(password) < 8:
            print("Пароль должен быть не короче 8 символов.")
            continue
        if password != password_repeat:
            print("Пароли не совпадают.")
            continue

        return password


def user_exists(login: str) -> bool:
    """Проверяет, есть ли пользователь с таким логином."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE login = %s LIMIT 1", (login,))
            return cur.fetchone() is not None


def create_admin(login: str, password: str) -> None:
    """Создаёт пользователя с ролью admin."""
    password_hash = make_password_hash(password)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (login, password_hash, role, doctor_id, patient_id)
                VALUES (%s, %s, 'admin', NULL, NULL)
                """,
                (login, password_hash),
            )


def main() -> None:
    print("Создание администратора МИС")
    login = ask_non_empty("Логин администратора: ")

    if user_exists(login):
        print(
            f"Пользователь {login!r} уже существует. "
            "Для смены пароля используйте scripts/reset_user_password.py"
        )
        raise SystemExit(1)

    password = ask_password_twice()
    create_admin(login, password)
    print(f"Администратор {login!r} создан. Пароль сохранён только как hash.")


if __name__ == "__main__":
    main()
