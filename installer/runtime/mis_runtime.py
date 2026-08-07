from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import locale
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
import zipfile

APP_TITLE = "МИС Нефрология — пилот"
DATA_DIR_NAME = "MIS Nephrology Pilot"
CONFIG_FILENAME = "config.json"
INITIALIZED_FILENAME = "initialized.json"
PID_FILENAME = "app.pid"
APP_HOST = "127.0.0.1"
DEFAULT_APP_PORT = 8000
DEFAULT_DB_PORT = 55432
DEFAULT_DB_NAME = "mis_nephrology_pilot"
DEFAULT_DB_USER = "mis_app"
EXPECTED_USERS = {
    "admin26_08": "admin",
    "zakharova_m": "doctor",
    "kazarkin_d": "doctor",
    "vozova_a": "department_head",
    "lobanova_n": "chief_physician",
    "kuznetsova_t": "doctor",
    "registrar": "registrar",
}


def _program_data() -> Path:
    raw = os.environ.get("PROGRAMDATA")
    if raw:
        return Path(raw)
    return Path.home() / "AppData" / "Local"


def default_data_root() -> Path:
    return _program_data() / DATA_DIR_NAME


def bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))


def install_root() -> Path:
    # EXE устанавливается в <install>\runtime\MIS_Nephrology_Runtime.exe.
    return Path(sys.executable).resolve().parent.parent


def message(text: str, *, title: str = APP_TITLE, error: bool = False) -> None:
    if os.name == "nt":
        flags = 0x10 if error else 0x40
        try:
            ctypes.windll.user32.MessageBoxW(None, text, title, flags)
            return
        except Exception:
            pass
    print(text, file=sys.stderr if error else sys.stdout)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path(data_root: Path) -> Path:
    return ensure_dir(data_root / "logs") / "runtime.log"


def log(data_root: Path, text: str) -> None:
    timestamp = dt.datetime.now().isoformat(timespec="seconds")
    with log_path(data_root).open("a", encoding="utf-8") as stream:
        stream.write(f"[{timestamp}] {text}\n")


def run_command(
    command: list[str],
    *,
    data_root: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    safe_command = " ".join(command)
    log(data_root, f"COMMAND: {safe_command}")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    result = subprocess.run(
        command,
        text=True,
        encoding=(locale.getpreferredencoding(False) if os.name == "nt" else "utf-8"),
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=creationflags,
        timeout=timeout,
        check=False,
    )
    if result.stdout:
        log(data_root, result.stdout.rstrip())
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Команда завершилась с кодом {result.returncode}: {safe_command}\n"
            f"Подробности: {log_path(data_root)}"
        )
    return result


def postgres_bin(name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    path = install_root() / "postgres" / "bin" / f"{name}{suffix}"
    if not path.is_file():
        raise RuntimeError(f"Не найден PostgreSQL-компонент: {path}")
    return path


def payload_path(name: str) -> Path:
    return install_root() / "payload" / name


def config_path(data_root: Path) -> Path:
    return data_root / CONFIG_FILENAME


def initialized_path(data_root: Path) -> Path:
    return data_root / INITIALIZED_FILENAME


def load_config(data_root: Path) -> dict:
    path = config_path(data_root)
    if not path.is_file():
        raise RuntimeError("Программа ещё не инициализирована. Повторите установку.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def random_secret(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def create_config(data_root: Path, app_port: int, db_port: int) -> dict:
    path = config_path(data_root)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))

    config = {
        "app_host": APP_HOST,
        "app_port": int(app_port),
        "db_host": APP_HOST,
        "db_port": int(db_port),
        "db_name": DEFAULT_DB_NAME,
        "db_user": DEFAULT_DB_USER,
        "db_password": random_secret(24),
        "postgres_superuser": "postgres",
        "postgres_password": random_secret(24),
        "session_secret_key": random_secret(48),
        "install_root": str(install_root()),
        "data_root": str(data_root),
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    save_json(path, config)
    return config


def copy_runtime_resources(data_root: Path) -> Path:
    source = bundle_root() / "app"
    if not source.is_dir():
        raise RuntimeError(f"В сборке отсутствуют ресурсы приложения: {source}")
    runtime_root = ensure_dir(data_root / "runtime")
    destination = runtime_root / "app"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return runtime_root


def copy_archive_payload(data_root: Path) -> Path:
    source = payload_path("medical_archive")
    destination = data_root / "medical_archive"
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    ensure_dir(destination)
    return destination


def write_postgres_configuration(config: dict, data_root: Path) -> None:
    pg_data = data_root / "postgres_data"
    logs = ensure_dir(data_root / "logs" / "postgres")
    conf = pg_data / "postgresql.conf"
    escaped_logs = str(logs).replace("\\", "/").replace("'", "''")
    with conf.open("a", encoding="utf-8") as stream:
        stream.write("\n# MIS Nephrology Pilot managed settings\n")
        stream.write("listen_addresses = '127.0.0.1'\n")
        stream.write(f"port = {int(config['db_port'])}\n")
        stream.write("password_encryption = 'scram-sha-256'\n")
        stream.write("max_connections = 30\n")
        stream.write("shared_buffers = '128MB'\n")
        stream.write("logging_collector = on\n")
        stream.write(f"log_directory = '{escaped_logs}'\n")
        stream.write("log_filename = 'postgresql-%Y-%m-%d.log'\n")
        stream.write("log_timezone = 'Europe/Moscow'\n")
        stream.write("timezone = 'Europe/Moscow'\n")

    hba = pg_data / "pg_hba.conf"
    hba.write_text(
        "# Generated by MIS Nephrology Pilot installer\n"
        "local all all scram-sha-256\n"
        "host all all 127.0.0.1/32 scram-sha-256\n"
        "host all all ::1/128 scram-sha-256\n",
        encoding="utf-8",
    )


def initialize_cluster(config: dict, data_root: Path) -> None:
    pg_data = data_root / "postgres_data"
    if (pg_data / "PG_VERSION").is_file():
        return

    if pg_data.exists():
        shutil.rmtree(pg_data)
    ensure_dir(pg_data)

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete=False, dir=data_root, suffix=".pw"
    ) as password_file:
        password_file.write(config["postgres_password"])
        password_path = Path(password_file.name)

    common = [
        str(postgres_bin("initdb")),
        "-D",
        str(pg_data),
        "-U",
        config["postgres_superuser"],
        f"--pwfile={password_path}",
        "--encoding=UTF8",
        "--auth-host=scram-sha-256",
        "--auth-local=trust",
    ]
    try:
        primary = common + ["--locale-provider=icu", "--icu-locale=ru-RU"]
        result = run_command(primary, data_root=data_root, check=False, timeout=180)
        if result.returncode != 0:
            log(data_root, "ICU locale initialization failed; retrying with locale C")
            shutil.rmtree(pg_data, ignore_errors=True)
            ensure_dir(pg_data)
            run_command(common + ["--locale=C"], data_root=data_root, timeout=180)
    finally:
        try:
            password_path.unlink()
        except FileNotFoundError:
            pass

    write_postgres_configuration(config, data_root)


def postgres_env(config: dict, *, app_user: bool) -> dict[str, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = (
        config["db_password"] if app_user else config["postgres_password"]
    )
    return env


def start_postgres(config: dict, data_root: Path) -> None:
    pg_data = data_root / "postgres_data"
    pg_ctl = str(postgres_bin("pg_ctl"))

    status = run_command(
        [pg_ctl, "status", "-D", str(pg_data)],
        data_root=data_root,
        check=False,
        timeout=20,
    )
    if status.returncode == 0:
        log(data_root, "PostgreSQL is already running")
        return

    launch_log = ensure_dir(data_root / "logs") / "postgres-launch.log"
    command = [
        pg_ctl,
        "start",
        "-D",
        str(pg_data),
        "-l",
        str(launch_log),
        "-W",
    ]
    log(data_root, "COMMAND: " + " ".join(command))

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    started = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        timeout=20,
        check=False,
    )
    if started.returncode != 0:
        raise RuntimeError(
            f"Не удалось запустить локальный PostgreSQL "
            f"(pg_ctl code {started.returncode}). "
            f"Журнал PostgreSQL: {launch_log}"
        )

    pg_isready = str(postgres_bin("pg_isready"))
    deadline = time.monotonic() + 60
    last_output = ""

    while time.monotonic() < deadline:
        try:
            probe = subprocess.run(
                [
                    pg_isready,
                    "--host",
                    str(config["db_host"]),
                    "--port",
                    str(config["db_port"]),
                    "--dbname",
                    "postgres",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding=(
                    locale.getpreferredencoding(False)
                    if os.name == "nt"
                    else "utf-8"
                ),
                errors="replace",
                creationflags=creationflags,
                timeout=5,
                check=False,
            )
            last_output = (probe.stdout or "").strip()
            if probe.returncode == 0:
                log(data_root, "PostgreSQL is ready on local port")
                return
        except subprocess.TimeoutExpired:
            last_output = "pg_isready timeout"

        time.sleep(1)

    raise RuntimeError(
        "Локальный PostgreSQL был запущен, но не стал готов к подключениям "
        f"за 60 секунд. Последняя проверка: {last_output or 'нет ответа'}. "
        f"Журнал PostgreSQL: {launch_log}"
    )


def stop_postgres(config: dict, data_root: Path) -> None:
    pg_data = data_root / "postgres_data"
    if not (pg_data / "PG_VERSION").is_file():
        return
    pg_ctl = str(postgres_bin("pg_ctl"))
    run_command(
        [pg_ctl, "stop", "-D", str(pg_data), "-m", "fast", "-w", "-t", "60"],
        data_root=data_root,
        check=False,
        timeout=75,
    )


def connect_kwargs(config: dict, *, app_user: bool, database: str | None = None) -> dict:
    return {
        "host": config["db_host"],
        "port": config["db_port"],
        "dbname": database or config["db_name"],
        "user": config["db_user"] if app_user else config["postgres_superuser"],
        "password": config["db_password"] if app_user else config["postgres_password"],
        "connect_timeout": 10,
    }


def create_role_and_database(config: dict, data_root: Path) -> None:
    import psycopg2
    from psycopg2 import sql

    connection = psycopg2.connect(**connect_kwargs(config, app_user=False, database="postgres"))
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (config["db_user"],))
            if cursor.fetchone() is None:
                cursor.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s").format(
                        sql.Identifier(config["db_user"])
                    ),
                    (config["db_password"],),
                )
            else:
                cursor.execute(
                    sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD %s").format(
                        sql.Identifier(config["db_user"])
                    ),
                    (config["db_password"],),
                )

            # Маркер успешной инициализации ещё не создан, поэтому существующая
            # одноимённая база означает незавершённую предыдущую попытку. Создаём
            # её заново, чтобы повторный запуск установщика был безопасным.
            cursor.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (config["db_name"],),
            )
            cursor.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier(config["db_name"])
                )
            )
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8'").format(
                    sql.Identifier(config["db_name"]),
                    sql.Identifier(config["db_user"]),
                )
            )
    finally:
        connection.close()
    log(data_root, "Database role and database are ready")


def restore_database(config: dict, data_root: Path) -> None:
    backup = payload_path("pilot_database.backup")
    if not backup.is_file():
        raise RuntimeError(f"Не найден снимок архивной базы: {backup}")

    run_command(
        [
            str(postgres_bin("pg_restore")),
            "--host",
            config["db_host"],
            "--port",
            str(config["db_port"]),
            "--username",
            config["db_user"],
            "--dbname",
            config["db_name"],
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            str(backup),
        ],
        data_root=data_root,
        env=postgres_env(config, app_user=True),
        timeout=3600,
    )
    log(data_root, "Pilot database restored")


def apply_pilot_passwords(config: dict, data_root: Path) -> None:
    import psycopg2

    sql_path = payload_path("pilot_passwords.sql")
    if not sql_path.is_file():
        raise RuntimeError(f"Не найден файл тестовых паролей: {sql_path}")
    statement = sql_path.read_text(encoding="utf-8")
    with psycopg2.connect(**connect_kwargs(config, app_user=True)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(statement)
    log(data_root, "Pilot account password hashes applied")


def verify_database(config: dict, data_root: Path) -> dict:
    import psycopg2

    with psycopg2.connect(**connect_kwargs(config, app_user=True)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT login, role, doctor_id FROM users WHERE login = ANY(%s)",
                (list(EXPECTED_USERS),),
            )
            rows = cursor.fetchall()
            actual = {login: (role, doctor_id) for login, role, doctor_id in rows}
            missing = sorted(set(EXPECTED_USERS) - set(actual))
            if missing:
                raise RuntimeError(f"После восстановления отсутствуют учётки: {', '.join(missing)}")
            for login, expected_role in EXPECTED_USERS.items():
                role, doctor_id = actual[login]
                if role != expected_role:
                    raise RuntimeError(
                        f"У {login} роль {role!r}, ожидалась {expected_role!r}"
                    )
                if expected_role in {"doctor", "department_head", "chief_physician"} and not doctor_id:
                    raise RuntimeError(f"Учётная запись {login} не привязана к врачу")

            counts: dict[str, int] = {}
            for table in (
                "patients",
                "appointments",
                "users",
                "schedule_entries",
                "audit_log",
                "audit_logs",
            ):
                cursor.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                if cursor.fetchone()[0]:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    counts[table] = int(cursor.fetchone()[0])
    log(data_root, f"Database verification passed: {counts}")
    return counts


def copy_guide(data_root: Path) -> Path:
    source = payload_path("Памятка_тестировщика_МИС.html")
    destination = data_root / source.name
    if source.is_file():
        shutil.copy2(source, destination)
    return destination


def initialize(args: argparse.Namespace) -> int:
    data_root = ensure_dir(Path(args.data_dir) if args.data_dir else default_data_root())
    try:
        log(data_root, "Initialization started")
        config = create_config(data_root, args.app_port, args.db_port)
        copy_runtime_resources(data_root)
        copy_archive_payload(data_root)
        copy_guide(data_root)

        if initialized_path(data_root).is_file():
            log(data_root, "Existing initialized database preserved")
            return 0

        initialize_cluster(config, data_root)
        start_postgres(config, data_root)
        create_role_and_database(config, data_root)
        restore_database(config, data_root)
        apply_pilot_passwords(config, data_root)
        counts = verify_database(config, data_root)
        marker = {
            "initialized_at": dt.datetime.now().isoformat(timespec="seconds"),
            "database": config["db_name"],
            "postgres_port": config["db_port"],
            "app_port": config["app_port"],
            "counts": counts,
        }
        save_json(initialized_path(data_root), marker)
        log(data_root, "Initialization completed successfully")
        return 0
    except Exception as exc:
        log(data_root, f"INITIALIZATION ERROR: {exc!r}")
        message(
            f"Установка базы МИС не завершена.\n\n{exc}\n\n"
            f"Журнал: {log_path(data_root)}",
            error=True,
        )
        return 1


def app_url(config: dict) -> str:
    return f"http://{config['app_host']}:{config['app_port']}/login"


def is_our_server_running(config: dict) -> bool:
    try:
        with urllib.request.urlopen(app_url(config), timeout=2) as response:
            content = response.read(65536).decode("utf-8", errors="ignore")
            return response.status == 200 and (
                "МИС Нефролога" in content or "Вход в систему" in content
            )
    except Exception:
        return False


def port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, int(port))) == 0


def set_application_environment(config: dict, data_root: Path) -> None:
    values = {
        "APP_ENV": "production",
        "ALLOWED_HOSTS": "localhost,127.0.0.1",
        "DB_HOST": config["db_host"],
        "DB_PORT": str(config["db_port"]),
        "DB_NAME": config["db_name"],
        "DB_USER": config["db_user"],
        "DB_PASSWORD": config["db_password"],
        "DB_POOL_MIN_CONN": "1",
        "DB_POOL_MAX_CONN": "10",
        "SESSION_SECRET_KEY": config["session_secret_key"],
        "SESSION_COOKIE_NAME": "mis_nephrology_pilot_session",
        "SESSION_COOKIE_MAX_AGE_SECONDS": "604800",
        "SESSION_IDLE_TIMEOUT_SECONDS": "3600",
        "SESSION_KEEPALIVE_INTERVAL_SECONDS": "180",
        "SESSION_HTTPS_ONLY": "false",
        "ARCHIVE_DOCUMENTS_ROOT": str(data_root / "medical_archive"),
    }
    os.environ.update(values)


def open_browser_when_ready(config: dict, data_root: Path) -> None:
    for _ in range(120):
        if is_our_server_running(config):
            webbrowser.open(app_url(config), new=2)
            return
        time.sleep(0.5)
    log(data_root, "Application did not become ready in 60 seconds")


def run_server(args: argparse.Namespace) -> int:
    data_root = Path(args.data_dir) if args.data_dir else default_data_root()
    try:
        config = load_config(data_root)
        if not initialized_path(data_root).is_file():
            raise RuntimeError("База приложения не была полностью инициализирована")
        start_postgres(config, data_root)

        if is_our_server_running(config):
            webbrowser.open(app_url(config), new=2)
            return 0
        if port_is_open(config["app_host"], config["app_port"]):
            raise RuntimeError(
                f"Порт {config['app_port']} занят другой программой. "
                "Закройте её или обратитесь к разработчику."
            )

        runtime_root = copy_runtime_resources(data_root)
        os.chdir(runtime_root)
        set_application_environment(config, data_root)
        (data_root / PID_FILENAME).write_text(str(os.getpid()), encoding="ascii")

        server_log = (ensure_dir(data_root / "logs") / "server-console.log").open(
            "a", encoding="utf-8", buffering=1
        )
        sys.stdout = server_log
        sys.stderr = server_log
        log(data_root, f"Starting web application at {app_url(config)}")

        threading.Thread(
            target=open_browser_when_ready,
            args=(config, data_root),
            daemon=True,
        ).start()

        import uvicorn

        uvicorn.run(
            "app.main:app",
            host=config["app_host"],
            port=int(config["app_port"]),
            log_level="info",
            access_log=False,
        )
        return 0
    except Exception as exc:
        log(data_root, f"RUN ERROR: {exc!r}")
        message(f"Не удалось запустить МИС.\n\n{exc}\n\nЖурнал: {log_path(data_root)}", error=True)
        return 1
    finally:
        pid = data_root / PID_FILENAME
        try:
            if pid.is_file() and pid.read_text(encoding="ascii").strip() == str(os.getpid()):
                pid.unlink()
        except Exception:
            pass


def stop_application(args: argparse.Namespace) -> int:
    data_root = Path(args.data_dir) if args.data_dir else default_data_root()
    try:
        config = load_config(data_root)
        pid_path = data_root / PID_FILENAME
        if pid_path.is_file():
            pid_text = pid_path.read_text(encoding="ascii").strip()
            # Не убиваем случайно другой процесс по устаревшему PID.
            # Сначала убеждаемся, что на локальном порту отвечает именно МИС.
            if (
                pid_text.isdigit()
                and int(pid_text) != os.getpid()
                and is_our_server_running(config)
            ):
                if os.name == "nt":
                    run_command(
                        ["taskkill", "/PID", pid_text, "/T", "/F"],
                        data_root=data_root,
                        check=False,
                        timeout=30,
                    )
                else:
                    os.kill(int(pid_text), 15)
            try:
                pid_path.unlink()
            except FileNotFoundError:
                pass
        stop_postgres(config, data_root)
        message("МИС и локальная база данных остановлены.")
        return 0
    except Exception as exc:
        log(data_root, f"STOP ERROR: {exc!r}")
        message(f"Не удалось полностью остановить МИС.\n\n{exc}", error=True)
        return 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def database_counts(config: dict) -> dict[str, int]:
    import psycopg2

    counts: dict[str, int] = {}
    with psycopg2.connect(**connect_kwargs(config, app_user=True)) as connection:
        with connection.cursor() as cursor:
            for table in (
                "patients",
                "appointments",
                "users",
                "schedule_entries",
                "audit_log",
                "audit_logs",
            ):
                cursor.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                if cursor.fetchone()[0]:
                    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                    counts[table] = int(cursor.fetchone()[0])
    return counts


def export_data(args: argparse.Namespace) -> int:
    data_root = Path(args.data_dir) if args.data_dir else default_data_root()
    try:
        config = load_config(data_root)
        start_postgres(config, data_root)
        documents = Path.home() / "Documents" / "MIS_Pilot_Exports"
        ensure_dir(documents)
        timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_zip = documents / f"MIS_Pilot_Export_{timestamp}.zip"

        temp_root = Path(tempfile.mkdtemp(prefix="mis-pilot-export-", dir=data_root))
        try:
            backup = temp_root / "database.backup"
            run_command(
                [
                    str(postgres_bin("pg_dump")),
                    "--host",
                    config["db_host"],
                    "--port",
                    str(config["db_port"]),
                    "--username",
                    config["db_user"],
                    "--dbname",
                    config["db_name"],
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    "--file",
                    str(backup),
                ],
                data_root=data_root,
                env=postgres_env(config, app_user=True),
                timeout=3600,
            )
            manifest = {
                "exported_at": dt.datetime.now().isoformat(timespec="seconds"),
                "database": config["db_name"],
                "database_backup_sha256": sha256(backup),
                "counts": database_counts(config),
                "contains_complete_database": True,
                "archive_documents_included": bool(args.include_archive),
                "note": (
                    "database.backup содержит полное состояние медицинской базы. "
                    "Исходные архивные документы неизменны и по умолчанию не дублируются."
                ),
            }
            save_json(temp_root / "manifest.json", manifest)
            (temp_root / "README.txt").write_text(
                "Выгрузка пилотного тестирования МИС Нефрология.\n"
                "database.backup — полный снимок PostgreSQL со всеми пациентами, "
                "приёмами, исследованиями, диагнозами, назначениями, расписанием и аудитом.\n"
                "Восстанавливать только в отдельную проверочную базу.\n",
                encoding="utf-8",
            )
            logs_target = temp_root / "logs"
            source_logs = data_root / "logs"
            if source_logs.is_dir():
                shutil.copytree(source_logs, logs_target, dirs_exist_ok=True)
            app_log = data_root / "runtime" / "app.log"
            if app_log.is_file():
                ensure_dir(logs_target)
                shutil.copy2(app_log, logs_target / "app.log")
            if args.include_archive:
                source_archive = data_root / "medical_archive"
                if source_archive.is_dir():
                    shutil.copytree(
                        source_archive,
                        temp_root / "medical_archive",
                        dirs_exist_ok=True,
                    )

            with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in temp_root.rglob("*"):
                    if path.is_file():
                        archive.write(path, path.relative_to(temp_root))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

        message(
            "Выгрузка завершена.\n\n"
            f"Файл: {output_zip}\n\n"
            "Он содержит полную медицинскую базу. Передавайте файл только защищённым способом."
        )
        if os.name == "nt":
            os.startfile(documents)  # type: ignore[attr-defined]
        return 0
    except Exception as exc:
        log(data_root, f"EXPORT ERROR: {exc!r}")
        message(f"Не удалось выгрузить данные.\n\n{exc}\n\nЖурнал: {log_path(data_root)}", error=True)
        return 1


def open_guide(args: argparse.Namespace) -> int:
    data_root = Path(args.data_dir) if args.data_dir else default_data_root()
    guide = data_root / "Памятка_тестировщика_МИС.html"
    if not guide.is_file():
        guide = payload_path("Памятка_тестировщика_МИС.html")
    if not guide.is_file():
        message("Памятка тестировщика не найдена.", error=True)
        return 1
    webbrowser.open(guide.resolve().as_uri(), new=2)
    return 0


def status(args: argparse.Namespace) -> int:
    data_root = Path(args.data_dir) if args.data_dir else default_data_root()
    try:
        config = load_config(data_root)
        postgres_state = "запущена"
        pg_status = run_command(
            [str(postgres_bin("pg_ctl")), "status", "-D", str(data_root / "postgres_data")],
            data_root=data_root,
            check=False,
            timeout=20,
        )
        if pg_status.returncode != 0:
            postgres_state = "остановлена"
        app_state = "запущено" if is_our_server_running(config) else "остановлено"
        message(
            f"Приложение: {app_state}\n"
            f"Локальная база: {postgres_state}\n"
            f"Адрес: {app_url(config)}\n"
            f"Данные: {data_root}"
        )
        return 0
    except Exception as exc:
        message(str(exc), error=True)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("initialize", parents=[common])
    init_parser.add_argument("--app-port", type=int, default=DEFAULT_APP_PORT)
    init_parser.add_argument("--db-port", type=int, default=DEFAULT_DB_PORT)
    init_parser.set_defaults(handler=initialize)

    run_parser = subparsers.add_parser("run", parents=[common])
    run_parser.set_defaults(handler=run_server)

    stop_parser = subparsers.add_parser("stop", parents=[common])
    stop_parser.set_defaults(handler=stop_application)

    export_parser = subparsers.add_parser("export", parents=[common])
    export_parser.add_argument("--include-archive", action="store_true")
    export_parser.set_defaults(handler=export_data)

    guide_parser = subparsers.add_parser("guide", parents=[common])
    guide_parser.set_defaults(handler=open_guide)

    status_parser = subparsers.add_parser("status", parents=[common])
    status_parser.set_defaults(handler=status)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
