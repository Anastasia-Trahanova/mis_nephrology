"""
Назначение файла: точка сборки FastAPI-приложения.

Как работает:
- создаёт FastAPI-приложение;
- отключает публичные /docs, /redoc, /openapi.json;
- подключает статические файлы /static;
- подключает middleware логирования, аудита, авторизации и cookie-сессий;
- подключает все роутеры проекта.

Что редактировать здесь:
- подключение новых роутеров и middleware;
- порядок middleware;
- общие настройки приложения.

Что не редактировать здесь:
- правила медицинских расчётов;
- SQL-запросы;
- HTML-разметку страниц.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

import logging
import time

from .routers import (
    admin,
    appointment_filters,
    appointment_pages,
    appointments,
    auth,
    ckd_registry,
    exports,
    home,
    lab_api,
    patient_pages,
    patients,
)
from .middleware.audit import AuditMiddleware
from .settings import settings


# Настройка логирования в файл.
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Техническое middleware логирования запросов.

    Важно:
    - логируем метод, путь, статус и длительность;
    - не логируем тело форм, пароли, диагнозы, назначения и другие медицинские данные.
    """

    async def dispatch(self, request, call_next):
        start_time = time.perf_counter()
        safe_path = request.url.path

        try:
            response = await call_next(request)
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            log_message = (
                f"{request.method} {safe_path} "
                f"- ERROR after {duration:.0f}ms: {repr(e)}"
            )
            print(log_message)
            logging.exception(log_message)
            raise

        duration = (time.perf_counter() - start_time) * 1000
        log_message = (
            f"{request.method} {safe_path} "
            f"- {response.status_code} - {duration:.0f}ms"
        )
        print(log_message)
        logging.info(log_message)
        return response


# docs_url/redoc_url/openapi_url отключены сознательно:
# внутренняя API-документация не должна быть публичной страницей МИС.
app = FastAPI(
    title="МИС Нефролога",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# /static/* — единственный технический публичный путь, потому что login-странице нужны CSS/JS.
# В static не должны лежать медицинские данные, выгрузки и персональная информация пациентов.
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# Подключаем middleware.
# Важно: SessionMiddleware добавляется последним, чтобы он был внешним слоем
# и request.session был доступен внутри AuthRequiredMiddleware.
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(auth.AuthRequiredMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_cookie_max_age_seconds,
    same_site="lax",
    https_only=settings.session_https_only,
)


# Подключаем роутеры: auth содержит /login, /logout и служебные endpoints сессии.
# Все остальные страницы закрываются AuthRequiredMiddleware.
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(home.router)
app.include_router(patient_pages.router)
app.include_router(appointment_pages.router)
app.include_router(lab_api.router)
app.include_router(exports.router)
app.include_router(appointment_filters.router)
app.include_router(patients.router)
app.include_router(appointments.router)
app.include_router(ckd_registry.router)
