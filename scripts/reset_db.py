"""
reset_db.py

Создает/пересоздает PostgreSQL-базу для разработки, применяет Alembic-миграции,
загружает тестовые данные и выполняет базовые проверки.

Обычный запуск из корня проекта:
    python scripts\reset_db.py --yes

По умолчанию скрипт:
  1) удаляет базу mis_for_registrations, если она есть;
  2) создает чистую базу;
  3) выполняет alembic upgrade head;
  4) загружает database/04 заполнение тестовыми данными.sql;
  5) выполняет проверки наполнения и запускает database/05 оценка целостности.sql.

Не запускать на базе с реальными данными.
"""

from __future__ import annotations

import argparse
import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2 import sql


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_DIR = PROJECT_ROOT / "database"
DEMO_DATA_FILE = DATABASE_DIR / "04 заполнение тестовыми данными.sql"
INTEGRITY_CHECK_FILE = DATABASE_DIR / "05 оценка целостности.sql"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Пересоздать dev-базу, применить Alembic-миграции, загрузить тестовые данные и проверить наполнение."
    )
    parser.add_argument("--host", default=os.getenv("DB_HOST", "localhost"), help="PostgreSQL host, default: localhost")
    parser.add_argument("--port", default=os.getenv("DB_PORT", "5432"), help="PostgreSQL port, default: 5432")
    parser.add_argument("--user", default=os.getenv("DB_USER", "postgres"), help="PostgreSQL user, default: postgres")
    parser.add_argument("--db-name", default=os.getenv("DB_NAME", "mis_for_registrations"), help="Имя создаваемой базы")
    parser.add_argument("--admin-db", default="postgres", help="База для административного подключения, default: postgres")
    parser.add_argument("--password", default=os.getenv("DB_PASSWORD"), help="Пароль. Лучше не передавать явно, скрипт спросит его сам.")
    parser.add_argument("--no-demo", action="store_true", help="Не загружать тестовые данные")
    parser.add_argument("--no-check", action="store_true", help="Не запускать проверки после создания")
    parser.add_argument("--no-drop", action="store_true", help="Не удалять/создавать базу, только применить миграции к существующей")
    parser.add_argument("--yes", action="store_true", help="Не спрашивать подтверждение удаления базы")
    return parser.parse_args()


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл: {path}")


def get_password(args: argparse.Namespace) -> str:
    if args.password:
        return args.password
    return getpass.getpass(f"Пароль пользователя PostgreSQL '{args.user}': ")


def connect(args: argparse.Namespace, dbname: str):
    return psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        dbname=dbname,
        client_encoding="UTF8",
    )


def confirm_drop(args: argparse.Namespace) -> None:
    if args.no_drop or args.yes:
        return
    print()
    print("ВНИМАНИЕ: база будет удалена и создана заново.")
    print(f"База: {args.db_name}")
    print("Не запускай это на базе с реальными данными.")
    answer = input("Для продолжения введи RESET: ").strip()
    if answer != "RESET":
        print("Отменено.")
        sys.exit(1)


def recreate_database(args: argparse.Namespace) -> None:
    if args.no_drop:
        print("[1/5] Пропускаю удаление/создание базы (--no-drop).")
        return

    print(f"[1/5] Пересоздаю базу {args.db_name}...")
    conn = connect(args, args.admin_db)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid();
                """,
                (args.db_name,),
            )
            cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(args.db_name)))
            cur.execute(
                sql.SQL("CREATE DATABASE {} WITH ENCODING 'UTF8' TEMPLATE template0").format(
                    sql.Identifier(args.db_name)
                )
            )
    finally:
        conn.close()
    print("     OK")


def build_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DB_HOST": str(args.host),
            "DB_PORT": str(args.port),
            "DB_USER": str(args.user),
            "DB_PASSWORD": str(args.password),
            "DB_NAME": str(args.db_name),
            "PGCLIENTENCODING": "UTF8",
            "PYTHONUTF8": "1",
        }
    )
    env["DATABASE_URL"] = f"postgresql://{args.user}:{args.password}@{args.host}:{args.port}/{args.db_name}"
    return env


def run_alembic(args: argparse.Namespace) -> None:
    print("[2/5] Применяю Alembic-миграции: alembic upgrade head...")
    cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
    subprocess.run(cmd, cwd=PROJECT_ROOT, env=build_env(args), check=True)
    print("     OK")


def execute_sql_file(args: argparse.Namespace, path: Path, title: str) -> None:
    require_file(path)
    print(title)
    sql_text = path.read_text(encoding="utf-8")
    conn = connect(args, args.db_name)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql_text)
    finally:
        conn.close()
    print("     OK")


def load_demo_data(args: argparse.Namespace) -> None:
    if args.no_demo:
        print("[3/5] Пропускаю тестовые данные (--no-demo).")
        return
    execute_sql_file(args, DEMO_DATA_FILE, "[3/5] Загружаю тестовые данные...")


def fetch_all(args: argparse.Namespace, query: str, params: tuple | None = None) -> list[tuple]:
    conn = connect(args, args.db_name)
    try:
        with conn.cursor() as cur:
            if params is None:
                cur.execute(query)
            else:
                cur.execute(query, params)
            return cur.fetchall()
    finally:
        conn.close()


def print_table(rows: Iterable[tuple]) -> None:
    for row in rows:
        print("     " + " | ".join(str(x) for x in row))


def run_basic_checks(args: argparse.Namespace) -> None:
    if args.no_check:
        print("[4/5] Пропускаю базовые проверки (--no-check).")
        return

    print("[4/5] Проверяю таблицы, view, наполнение и стадии ХБП...")

    table_rows = fetch_all(
        args,
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
        """,
    )
    print(f"     Таблиц найдено: {len(table_rows)}")

    view_rows = fetch_all(
        args,
        """
        SELECT table_name
        FROM information_schema.views
        WHERE table_schema = 'public'
        ORDER BY table_name;
        """,
    )
    print("     View:")
    print_table(view_rows or [("нет",)])

    counts = fetch_all(
        args,
        """
        SELECT 'companies' AS table_name, COUNT(*) FROM companies
        UNION ALL SELECT 'branches', COUNT(*) FROM branches
        UNION ALL SELECT 'locations', COUNT(*) FROM locations
        UNION ALL SELECT 'doctors', COUNT(*) FROM doctors
        UNION ALL SELECT 'patients', COUNT(*) FROM patients
        UNION ALL SELECT 'users', COUNT(*) FROM users
        UNION ALL SELECT 'appointments', COUNT(*) FROM appointments
        UNION ALL SELECT 'icd10_diagnoses', COUNT(*) FROM icd10_diagnoses
        UNION ALL SELECT 'calculated_metrics', COUNT(*) FROM calculated_metrics
        ORDER BY table_name;
        """,
    )
    print("     Наполнение ключевых таблиц:")
    print_table(counts)

    stages = fetch_all(
        args,
        """
        SELECT ckd_stage, COUNT(*)
        FROM calculated_metrics
        GROUP BY ckd_stage
        ORDER BY ckd_stage;
        """,
    )
    print("     Стадии ХБП в calculated_metrics:")
    print_table(stages or [("нет данных", 0)])

    wrong_stage = fetch_all(
        args,
        """
        SELECT COUNT(*)
        FROM calculated_metrics
        WHERE ckd_stage LIKE 'G%%' OR ckd_stage LIKE 'C%%';
        """,
    )[0][0]
    if wrong_stage != 0:
        raise RuntimeError(f"Найдены старые стадии G*/латинские C*: {wrong_stage}")
    print("     Старых G*/латинских C* стадий нет: OK")


def run_integrity_sql(args: argparse.Namespace) -> None:
    if args.no_check:
        print("[5/5] Пропускаю файл проверки целостности (--no-check).")
        return
    require_file(INTEGRITY_CHECK_FILE)

    print("[5/5] Запускаю database/05 оценка целостности.sql через psql...")
    psql_path = shutil.which("psql")
    if not psql_path:
        print("     psql не найден в PATH. Базовые проверки уже выполнены, файл 05 можно запустить вручную через psql/DBeaver.")
        return

    env = build_env(args)
    env["PGPASSWORD"] = str(args.password)
    cmd = [
        psql_path,
        "-h",
        str(args.host),
        "-p",
        str(args.port),
        "-U",
        str(args.user),
        "-d",
        str(args.db_name),
        "-v",
        "ON_ERROR_STOP=1",
        "-f",
        str(INTEGRITY_CHECK_FILE),
    ]
    subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=True)
    print("     OK")


def main() -> None:
    args = parse_args()
    args.password = get_password(args)

    require_file(PROJECT_ROOT / "alembic.ini")
    require_file(PROJECT_ROOT / "migrations" / "env.py")
    require_file(PROJECT_ROOT / "migrations" / "versions" / "0001_baseline_schema.py")
    require_file(DATABASE_DIR / "01 создание таблиц.sql")
    require_file(DATABASE_DIR / "02 настройка связей ключей и ограничений.sql")
    require_file(DATABASE_DIR / "03 создание и заполнение таблиц МКБ.sql")

    confirm_drop(args)
    recreate_database(args)
    run_alembic(args)
    load_demo_data(args)
    run_basic_checks(args)
    run_integrity_sql(args)

    print()
    print("Готово. База создана и проверена.")
    print(f"DB_NAME={args.db_name}")
    print("Для подключения в DBeaver:")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Database: {args.db_name}")
    print(f"  User: {args.user}")


if __name__ == "__main__":
    main()
