from __future__ import annotations

import logging
import time

from fastapi import Depends, FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .middleware.audit import AuditMiddleware
from .routers import (
    admin,
    appointment_filters,
    appointment_pages,
    appointments,
    auth,
    ckd_registry,
    clinical_reference,
    exports,
    home,
    lab_api,
    patient_pages,
    patients,
    schedule,
)
from .settings import settings


logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000
            log_message = (
                f"{request.method} {request.url.path} "
                f"- ERROR after {duration:.0f}ms: {exc!r}"
            )
            print(log_message)
            logging.exception(log_message)
            raise
        duration = (time.perf_counter() - start_time) * 1000
        log_message = (
            f"{request.method} {request.url.path} "
            f"- {response.status_code} - {duration:.0f}ms"
        )
        print(log_message)
        logging.info(log_message)
        return response


app = FastAPI(
    title="МИС Нефролога",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.exception_handler(auth.AuthenticationRequired)
async def authentication_required_handler(
    request: Request,
    exc: auth.AuthenticationRequired,
):
    return auth.unauthorized_response(request, exc.reason)


# Middleware добавляются изнутри наружу:
# TrustedHost -> Session -> Audit -> Logging -> приложение.
# Поэтому аудит видит пользователя из request.session.
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_cookie_max_age_seconds,
    same_site="lax",
    https_only=settings.session_https_only,
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts,
    www_redirect=False,
)

protected_dependencies = [Depends(auth.require_authenticated_user)]


@app.get(
    "/openapi.json",
    dependencies=protected_dependencies,
    include_in_schema=False,
)
def protected_openapi():
    return JSONResponse(app.openapi())


@app.get(
    "/docs",
    dependencies=protected_dependencies,
    include_in_schema=False,
)
def protected_docs():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{app.title} — Swagger UI",
    )


@app.get(
    "/redoc",
    dependencies=protected_dependencies,
    include_in_schema=False,
)
def protected_redoc():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{app.title} — ReDoc",
    )


# /login остаётся публичным. Logout и session endpoints защищены в auth.router.
app.include_router(auth.router)
# Все рабочие разделы требуют только активную сессию.
# Ограничения «врач видит только своих пациентов» здесь намеренно нет.
app.include_router(home.router, dependencies=protected_dependencies)
app.include_router(patient_pages.router, dependencies=protected_dependencies)
app.include_router(appointment_pages.router, dependencies=protected_dependencies)
app.include_router(lab_api.router, dependencies=protected_dependencies)
app.include_router(exports.router, dependencies=protected_dependencies)
app.include_router(appointment_filters.router, dependencies=protected_dependencies)
app.include_router(patients.router, dependencies=protected_dependencies)
app.include_router(appointments.router, dependencies=protected_dependencies)
app.include_router(clinical_reference.router, dependencies=protected_dependencies)
app.include_router(ckd_registry.router, dependencies=protected_dependencies)
app.include_router(admin.router, dependencies=protected_dependencies)
app.include_router(schedule.router, dependencies=protected_dependencies)
