from __future__ import annotations

import logging
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

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
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            log_message = (
                f"{request.method} {request.url.path}"
                f"{'?' + request.url.query if request.url.query else ''} "
                f"- ERROR after {duration:.0f}ms: {repr(e)}"
            )
            print(log_message)
            logging.exception(log_message)
            raise

        duration = (time.perf_counter() - start_time) * 1000
        log_message = (
            f"{request.method} {request.url.path}"
            f"{'?' + request.url.query if request.url.query else ''} "
            f"- {response.status_code} - {duration:.0f}ms"
        )
        print(log_message)
        logging.info(log_message)
        return response


app = FastAPI(title="МИС Нефролога", version="1.0.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Важно: SessionMiddleware добавляется последним, чтобы он был внешним слоем
# и request.session был доступен внутри AuthRequiredMiddleware.
app.add_middleware(LoggingMiddleware)
app.add_middleware(auth.AuthRequiredMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    same_site="lax",
    https_only=False,  # Для локальной разработки. На сервере с HTTPS поставить True.
)

# Подключаем роутеры: auth доступен без входа, остальные закрываются middleware.
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(patient_pages.router)
app.include_router(appointment_pages.router)
app.include_router(lab_api.router)
app.include_router(exports.router)
app.include_router(appointment_filters.router)
app.include_router(patients.router)
app.include_router(appointments.router)
app.include_router(ckd_registry.router)
app.include_router(admin.router)
app.include_router(schedule.router)
