import base64
import hashlib
import hmac
import secrets
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.connection import get_db_connection

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


PUBLIC_PATHS = {
    "/login",
    "/logout",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}


def is_public_path(path: str) -> bool:
    """Пути, которые доступны без авторизации."""
    return path in PUBLIC_PATHS or path.startswith("/static/")


def safe_next_url(next_url: Optional[str]) -> str:
    """
    Защита от open redirect: после входа разрешаем переход только на локальный путь сайта.
    """
    if not next_url:
        return "/"

    next_url = str(next_url).strip()

    if not next_url.startswith("/"):
        return "/"

    if next_url.startswith("//"):
        return "/"

    if "\r" in next_url or "\n" in next_url:
        return "/"

    return next_url


class AuthRequiredMiddleware(BaseHTTPMiddleware):
    """
    Базовая защита приложения:
    - /login и служебные пути открыты;
    - все HTML-страницы без сессии отправляются на /login;
    - API без сессии возвращает 401 JSON.

    Это пока только факт входа в систему. Ролевые ограничения врач/admin добавим следующим шагом.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if is_public_path(path):
            return await call_next(request)

        if not request.session.get("user_id"):
            if path.startswith("/api/"):
                return JSONResponse(
                    {"detail": "Требуется вход в систему"},
                    status_code=401,
                )

            next_url = path
            if request.url.query:
                next_url += "?" + request.url.query

            return RedirectResponse(
                url=f"/login?next={quote(next_url, safe='')}",
                status_code=303,
            )

        return await call_next(request)


def make_password_hash(password: str, iterations: int = 260000) -> str:
    """
    Создаёт хэш пароля без внешних зависимостей.
    Формат хранения:
        pbkdf2_sha256$iterations$salt_base64$hash_base64
    """
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Проверяет пароль по хэшу pbkdf2_sha256."""
    if not password or not stored_hash:
        return False

    try:
        algorithm, iterations_str, salt_b64, hash_b64 = stored_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        # Старые заглушки или bcrypt-строки сюда не подходят.
        # Для теста обнови users через SQL-файл из этого пакета.
        return False

    try:
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
    except Exception:
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )

    return hmac.compare_digest(actual, expected)


def get_user_by_login(login: str):
    """Возвращает пользователя по логину."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    u.id,
                    u.login,
                    u.password_hash,
                    u.role,
                    u.doctor_id,
                    u.patient_id,
                    CASE
                        WHEN u.role = 'doctor' THEN
                            d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '')
                        WHEN u.role = 'patient' THEN
                            p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '')
                        ELSE
                            'Администратор'
                    END AS display_name
                FROM users u
                LEFT JOIN doctors d ON d.id = u.doctor_id
                LEFT JOIN patients p ON p.id = u.patient_id
                WHERE u.login = %s
                LIMIT 1
                """,
                (login,),
            )
            return cur.fetchone()


def put_user_into_session(request: Request, user) -> None:
    """Сохраняет минимально нужные данные пользователя в сессию."""
    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["login"] = user["login"]
    request.session["role"] = user["role"]
    request.session["doctor_id"] = user.get("doctor_id")
    request.session["patient_id"] = user.get("patient_id")
    request.session["display_name"] = user.get("display_name") or user["login"]


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/"):
    if request.session.get("user_id"):
        return RedirectResponse(url=safe_next_url(next), status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "next": safe_next_url(next),
            "error": None,
        },
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    next_url = safe_next_url(next)
    user = get_user_by_login(login.strip())

    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "next": next_url,
                "error": "Неверный логин или пароль",
                "login": login,
            },
            status_code=401,
        )

    put_user_into_session(request, user)
    return RedirectResponse(url=next_url, status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
