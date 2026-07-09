"""
Назначение файла: сброс пароля пользователя без удаления учётной записи.

Как работает:
- запускается разработчиком/администратором вручную;
- принимает логин аргументом или спрашивает его в терминале;
- спрашивает новый пароль;
- обновляет только users.password_hash;
- учётка, роль, doctor_id/patient_id и связанные медицинские данные не удаляются.

Когда использовать:
- если разработчик забыл пароль администратора;
- если врачу надо выдать новый пароль;
- если старый password_hash был в неподдерживаемом формате.

Что редактировать здесь:
- правила валидации нового пароля;
- дополнительные проверки роли пользователя.

Что не редактировать здесь:
- хранение открытых паролей;
- медицинские таблицы;
- авторизацию в браузере.
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


def ask_login() -> str:
    """Берёт логин из argv или спрашивает в терминале."""
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        return sys.argv[1].strip()

    while True:
        login = input("Логин пользователя: ").strip()
        if login:
            return login
        print("Логин не должен быть пустым.")


def ask_password_twice() -> str:
    """Запрашивает новый пароль два раза."""
    while True:
        password = getpass("Новый пароль: ")
        password_repeat = getpass("Повторите новый пароль: ")

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


def reset_password(login: str, password: str) -> bool:
    """
    Обновляет password_hash.

    Возвращает True, если пользователь найден и обновлён.
    """
    password_hash = make_password_hash(password)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET password_hash = %s
                WHERE login = %s
                RETURNING id
                """,
                (password_hash, login),
            )
            return cur.fetchone() is not None


def main() -> None:
    print("Сброс пароля пользователя МИС")
    login = ask_login()
    password = ask_password_twice()

    if not reset_password(login, password):
        print(f"Пользователь {login!r} не найден.")
        raise SystemExit(1)

    print(f"Пароль пользователя {login!r} обновлён. В БД сохранён только hash.")


if __name__ == "__main__":
    main()
