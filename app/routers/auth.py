"""
Назначение файла: вход в систему, выход и базовая защита внутренних страниц.

Как работает:
- /login доступен без входа;
- /static/* пропускается как технический путь для CSS/JS;
- все остальные страницы требуют active session;
- /logout не является публичной страницей: без сессии отправляет на /login,
  с сессией очищает её и завершает вход;
- /auth/session/keepalive продлевает сессию, когда врач реально работает на странице;
- /auth/session/status помогает JS проверить сессию перед отправкой формы;
- пароли проверяются только по password_hash, открытые пароли не хранятся.

Что редактировать здесь:
- список публичных путей;
- правила idle-timeout;
- логику login/logout;
- формат хэша пароля.

Что не редактировать здесь:
- ролевые права doctor/admin — они вынесены в app/security/permissions.py;
- медицинские маршруты;
- шаблоны карточки пациента и формы приёма.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.db.connection import get_db_connection
from app.repositories.audit_log import log_audit_event
from app.settings import settings


router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


LOGIN_PATH = "/login"
STATIC_PREFIX = "/static/"
SESSION_KEEPALIVE_PATH = "/auth/session/keepalive"
SESSION_STATUS_PATH = "/auth/session/status"


IDLE_EXPIRED_MESSAGE = (
    "Сессия истекла из-за бездействия. "
    "Войдите снова, чтобы продолжить работу."
)


def now_ts() -> int:
    """Возвращает текущее Unix-время в секундах для хранения в session."""
    return int(time.time())


def is_public_path(path: str) -> bool:
    """
    Проверяет, можно ли открыть путь без авторизации.

    По требованиям проекта публична только страница входа /login.
    /static/* открыт технически, потому что браузеру нужны CSS/JS для страницы входа.
    /logout, /docs, /redoc, /openapi.json не публичные.
    """
    return path == LOGIN_PATH or path.startswith(STATIC_PREFIX)


def is_async_or_api_request(request: Request) -> bool:
    """
    Отличает API/JS-запросы от обычных HTML-переходов.

    Для HTML без сессии делаем redirect на /login.
    Для API/JS без сессии возвращаем 401 JSON, чтобы скрипт мог показать предупреждение
    и не отправлять форму с введёнными данными в пустоту.
    """
    path = request.url.path
    accept = request.headers.get("accept", "")
    requested_with = request.headers.get("x-requested-with", "")

    return (
        path.startswith("/api/")
        or path.startswith("/auth/session/")
        or requested_with.lower() == "xmlhttprequest"
        or "application/json" in accept.lower()
    )


def safe_next_url(next_url: Optional[str]) -> str:
    """
    Защита от open redirect.

    После входа разрешаем переход только на локальный путь сайта:
    /patient/1 — можно;
    https://evil.example — нельзя;
    //evil.example — нельзя.
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


def current_next_url(request: Request) -> str:
    """Собирает текущий путь с query string для возврата после логина."""
    next_url = request.url.path
    if request.url.query:
        next_url += "?" + request.url.query
    return safe_next_url(next_url)


def mark_session_activity(request: Request) -> None:
    """
    Обновляет timestamp последней активности пользователя.

    Этот timestamp хранится в подписанной session-cookie.
    Он не содержит медицинских данных и нужен только для idle-timeout.
    """
    request.session["last_seen_at"] = now_ts()


def session_is_active(request: Request) -> tuple[bool, str | None]:
    """
    Проверяет активность сессии.

    Возвращает:
    - (True, None), если пользователь вошёл и idle-timeout не истёк;
    - (False, reason), если входа нет или сессия устарела.

    Absolute timeout на этом этапе сознательно не используется.
    """
    if not request.session.get("user_id"):
        return False, "not_authenticated"

    last_seen_at = request.session.get("last_seen_at")
    try:
        last_seen_at_int = int(last_seen_at)
    except (TypeError, ValueError):
        return False, "missing_last_seen_at"

    idle_seconds = now_ts() - last_seen_at_int
    if idle_seconds > settings.session_idle_timeout_seconds:
        return False, "idle_timeout"

    return True, None


def unauthorized_response(request: Request, reason: str | None = None):
    """
    Возвращает правильный ответ для неавторизованного запроса.

    HTML-страницы отправляем на /login?next=...
    API/JS получают 401 JSON.
    """
    request.session.clear()

    if is_async_or_api_request(request):
        return JSONResponse(
            {
                "authenticated": False,
                "detail": IDLE_EXPIRED_MESSAGE
                if reason in {"idle_timeout", "missing_last_seen_at"}
                else "Требуется вход в систему",
                "reason": reason or "not_authenticated",
            },
            status_code=401,
        )

    next_url = quote(current_next_url(request), safe="")
    return RedirectResponse(url=f"/login?next={next_url}", status_code=303)


class AuthRequiredMiddleware(BaseHTTPMiddleware):
    """
    Центральная защита приложения.

    Здесь закрываются внутренние страницы, а не отдельные пункты меню.
    Поэтому прямой переход в адресной строке на /patient/1 или /export/1/docx
    без active session тоже будет заблокирован.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if is_public_path(path):
            return await call_next(request)

        active, reason = session_is_active(request)
        if not active:
            return unauthorized_response(request, reason)

        # Запрос дошёл до защищённой части приложения — пользователь активен.
        # Дополнительно JS keepalive будет поддерживать last_seen_at во время заполнения форм.
        mark_session_activity(request)
        return await call_next(request)


def make_password_hash(password: str, iterations: int = 260000) -> str:
    """
    Создаёт хэш пароля без внешних зависимостей.

    Формат хранения:
    pbkdf2_sha256$iterations$salt_base64$hash_base64

    В БД попадает только хэш. Открытый пароль не сохраняется.
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
        # Для восстановления доступа используй scripts/reset_user_password.py.
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
                        ELSE 'Администратор'
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
    """
    Сохраняет минимально нужные данные пользователя в сессию.

    В сессии нет медицинских данных пациента.
    last_seen_at нужен для отключения после бездействия.
    """
    timestamp = now_ts()

    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["login"] = user["login"]
    request.session["role"] = user["role"]
    request.session["doctor_id"] = user.get("doctor_id")
    request.session["patient_id"] = user.get("patient_id")
    request.session["display_name"] = user.get("display_name") or user["login"]
    request.session["login_at"] = timestamp
    request.session["last_seen_at"] = timestamp


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/"):
    """Показывает страницу входа."""
    next_url = safe_next_url(next)

    # Если пользователь уже вошёл, повторно страницу login не показываем.
    active, _ = session_is_active(request)
    if active:
        return RedirectResponse(url=next_url, status_code=303)

    request.session.clear()
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "next": next_url,
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
    """Проверяет логин/пароль и создаёт новую active session."""
    next_url = safe_next_url(next)
    login_value = login.strip()
    user = get_user_by_login(login_value)

    if not user or not verify_password(password, user["password_hash"]):
        log_audit_event(
            request,
            "login_failed",
            result="error",
            user_login=login_value,
            details="неуспешная попытка входа",
            error_message="неверный логин или пароль",
            status_code=401,
        )
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
    log_audit_event(
        request,
        "login_success",
        details="успешный вход в систему",
        status_code=303,
    )
    return RedirectResponse(url=next_url, status_code=303)


@router.get("/logout")
def logout(request: Request):
    """
    Служебный выход из системы.

    /logout не показывает медицинские данные и не является публичной страницей.
    Если сессия активна — очищает её. Если нет — middleware уже отправит на /login.
    """
    log_audit_event(
        request,
        "logout",
        details="пользователь завершил работу",
        status_code=303,
    )
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.post(SESSION_KEEPALIVE_PATH)
def session_keepalive(request: Request):
    """
    Продлевает сессию во время реальной работы врача.

    JS вызывает этот endpoint только если врач вводил данные, кликал или менял поля.
    Медицинские данные через keepalive не передаются.
    """
    mark_session_activity(request)
    return {
        "authenticated": True,
        "expires_in_seconds": settings.session_idle_timeout_seconds,
    }


@router.get(SESSION_STATUS_PATH)
def session_status(request: Request):
    """
    Проверяет сессию перед отправкой формы.

    Если сессия истекла, middleware вернёт 401 JSON до входа в этот обработчик.
    Если дошли сюда — сессия активна.
    """
    return {
        "authenticated": True,
        "expires_in_seconds": settings.session_idle_timeout_seconds,
    }
