from fastapi import FastAPI
from .routers import pages, patients, auth, ckd_registry, appointments, appointment_filters
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
import time
import logging
from .settings import settings

# Настройка логирования в файл
logging.basicConfig(
    filename="app.log",  # файл, куда будут сохраняться логи
    level=logging.INFO,  # уровень важности (INFO и выше)
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Middleware для измерения времени запросов

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

# Подключаем middleware.
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

# Подключаем роутеры: auth должен быть доступен без входа, остальные закрываются middleware.
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(appointment_filters.router)
app.include_router(patients.router)
app.include_router(appointments.router)
app.include_router(ckd_registry.router)
