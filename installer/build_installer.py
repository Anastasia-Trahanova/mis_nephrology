from __future__ import annotations

import argparse
import base64
import datetime as dt
import getpass
import hashlib
import html
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import string
import subprocess
import sys
import urllib.request
import venv

INSTALLER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = INSTALLER_DIR.parent
PRIVATE_DIR = INSTALLER_DIR / "private"
WORK_DIR = INSTALLER_DIR / "work"
OUTPUT_DIR = INSTALLER_DIR / "output"
RUNTIME_SOURCE = INSTALLER_DIR / "runtime" / "mis_runtime.py"
ISS_TEMPLATE = INSTALLER_DIR / "templates" / "MIS_Nephrology_Pilot.iss.template"
CREDENTIALS_FILE = PRIVATE_DIR / "pilot_credentials.env"
VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
PYINSTALLER_VERSION = "6.20.0"

EXPECTED_USERS = [
    ("admin26_08", "admin", "Администратор"),
    ("zakharova_m", "doctor", "Врач — Захарова М. В."),
    ("kazarkin_d", "doctor", "Врач — Казаркин Д. Г."),
    ("vozova_a", "department_head", "Заведующий отделением — Возова А. М."),
    ("lobanova_n", "chief_physician", "Главный врач — Лобанова Н. А."),
    ("kuznetsova_t", "doctor", "Врач — Кузнецова Т. Е."),
    ("registrar", "registrar", "Регистратор"),
]
CLINICAL_ROLES = {"doctor", "department_head", "chief_physician"}


def print_step(number: int, text: str) -> None:
    print(f"\n[{number}] {text}")


def run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    print("  >", subprocess.list2cmdline(command))
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        check=False,
    )
    if capture and result.stdout:
        print(result.stdout.rstrip())
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Команда завершилась с кодом {result.returncode}: "
            f"{subprocess.list2cmdline(command)}"
        )
    return result


def require_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("Установщик Windows нужно собирать на Windows 10/11 x64.")
    if sys.maxsize <= 2**32:
        raise RuntimeError("Для сборки нужен 64-битный Python.")


def parse_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        result[key] = value
    return result


def validate_project() -> dict[str, str]:
    required = [
        PROJECT_ROOT / "app" / "main.py",
        PROJECT_ROOT / "requirements.txt",
        PROJECT_ROOT / ".env",
        RUNTIME_SOURCE,
        ISS_TEMPLATE,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError("Не найдены обязательные файлы:\n" + "\n".join(missing))
    return parse_env_file(PROJECT_ROOT / ".env")


def find_postgres_bin(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    for executable in ("pg_dump", "postgres"):
        found = shutil.which(executable)
        if found:
            candidates.append(Path(found).resolve().parent)
    postgres_home = os.environ.get("POSTGRES_HOME")
    if postgres_home:
        candidates.append(Path(postgres_home) / "bin")
    for base_name in ("ProgramFiles", "ProgramW6432"):
        base = os.environ.get(base_name)
        if base:
            root = Path(base) / "PostgreSQL"
            if root.is_dir():
                candidates.extend(sorted(root.glob("*/bin"), reverse=True))

    checked: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.expanduser().resolve()
        if candidate in checked:
            continue
        checked.add(candidate)
        if all((candidate / name).is_file() for name in (
            "postgres.exe", "pg_dump.exe", "pg_restore.exe", "initdb.exe", "pg_ctl.exe", "psql.exe"
        )):
            version = run([str(candidate / "postgres.exe"), "--version"], capture=True).stdout or ""
            match = re.search(r"(\d+)\.(\d+)", version)
            if match and int(match.group(1)) == 18:
                print(f"  PostgreSQL runtime: {candidate} ({version.strip()})")
                return candidate
    raise RuntimeError(
        "Не найден PostgreSQL 18 x64. Передайте --postgres-bin или добавьте PostgreSQL 18 в PATH."
    )


def pg_env(project_env: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = project_env["DB_PASSWORD"]
    return env


def psql_query(pg_bin: Path, project_env: dict[str, str], query: str) -> list[str]:
    command = [
        str(pg_bin / "psql.exe"),
        "--host", project_env.get("DB_HOST", "127.0.0.1"),
        "--port", project_env.get("DB_PORT", "5432"),
        "--username", project_env["DB_USER"],
        "--dbname", project_env["DB_NAME"],
        "--no-psqlrc",
        "--tuples-only",
        "--no-align",
        "--field-separator", "|",
        "--command", query,
    ]
    result = run(command, env=pg_env(project_env), capture=True)
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


def verify_source_database(pg_bin: Path, project_env: dict[str, str]) -> None:
    required = ("DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if not project_env.get(name)]
    if missing:
        raise RuntimeError(f"В .env не заполнены: {', '.join(missing)}")

    info = psql_query(
        pg_bin,
        project_env,
        "SELECT current_database(), current_setting('server_version');",
    )
    if len(info) != 1:
        raise RuntimeError("Не удалось определить текущую базу PostgreSQL.")
    database_name, version = info[0].split("|", 1)
    print(f"  Исходная база: {database_name}; PostgreSQL {version}")
    if not version.startswith("18."):
        raise RuntimeError("Снимок пилота должен собираться с PostgreSQL 18.x.")

    quoted_logins = ",".join("'" + login.replace("'", "''") + "'" for login, _, _ in EXPECTED_USERS)
    rows = psql_query(
        pg_bin,
        project_env,
        (
            "SELECT login, role, COALESCE(doctor_id::text, '') "
            f"FROM users WHERE login IN ({quoted_logins}) ORDER BY login;"
        ),
    )
    actual: dict[str, tuple[str, str]] = {}
    for row in rows:
        login, role, doctor_id = row.split("|", 2)
        actual[login] = (role, doctor_id)

    for login, role, _ in EXPECTED_USERS:
        if login == "admin26_08" and login not in actual:
            print("  Администратор admin26_08 будет создан установщиком.")
            continue
        if login not in actual:
            raise RuntimeError(f"В исходной базе отсутствует учётная запись {login!r}.")
        actual_role, doctor_id = actual[login]
        if actual_role != role:
            raise RuntimeError(
                f"У {login} роль {actual_role!r}, ожидалась {role!r}."
            )
        if role in CLINICAL_ROLES and not doctor_id:
            raise RuntimeError(f"Учётная запись {login} не привязана к doctors.id.")
    print("  Учётные записи и врачебные привязки проверены.")


def get_archive_root(args: argparse.Namespace, project_env: dict[str, str]) -> Path:
    raw = args.archive_root or project_env.get("ARCHIVE_DOCUMENTS_ROOT")
    if not raw:
        raise RuntimeError(
            "Не указан ARCHIVE_DOCUMENTS_ROOT. Добавьте его в .env или передайте --archive-root."
        )
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if not path.is_dir():
        raise RuntimeError(f"Не найдена папка архивных документов: {path}")
    return path


def verify_archive_files(pg_bin: Path, project_env: dict[str, str], archive_root: Path) -> int:
    query = (
        "SELECT archive_source_relative_path, archive_import_key "
        "FROM appointments "
        "WHERE is_archive_import IS TRUE "
        "AND archive_source_relative_path IS NOT NULL "
        "ORDER BY id;"
    )
    rows = psql_query(pg_bin, project_env, query)
    if not rows:
        print("  В базе нет архивных документов с сохранёнными путями.")
        return 0

    stable_key = re.compile(r"^nephro-archive-v1:([0-9a-fA-F]{64}):\d+$")
    failures: list[str] = []
    for index, row in enumerate(rows, start=1):
        relative, import_key = row.split("|", 1)
        normalized = relative.replace("\\", "/").strip("/")
        parts = [part for part in normalized.split("/") if part not in {"", "."}]
        if not parts or any(part == ".." for part in parts):
            failures.append(f"Недопустимый путь: {relative}")
            continue
        candidate = archive_root.joinpath(*parts).resolve()
        try:
            candidate.relative_to(archive_root)
        except ValueError:
            failures.append(f"Путь выходит из архива: {relative}")
            continue
        if not candidate.is_file():
            failures.append(f"Файл не найден: {relative}")
            continue
        if candidate.suffix.lower() not in {".doc", ".docx", ".pdf"}:
            failures.append(f"Недопустимый тип архивного файла: {relative}")
            continue
        match = stable_key.fullmatch(import_key.strip())
        if not match:
            failures.append(f"Некорректный archive_import_key: {relative}")
            continue
        digest = hashlib.sha256()
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != match.group(1).lower():
            failures.append(f"SHA-256 не совпадает: {relative}")
        if index % 100 == 0:
            print(f"  Проверено документов: {index}/{len(rows)}")

    if failures:
        preview = "\n".join(f"- {item}" for item in failures[:20])
        raise RuntimeError(
            f"Проверка архива не пройдена ({len(failures)} ошибок):\n{preview}"
        )
    print(f"  Архив проверен: {len(rows)} документов.")
    return len(rows)


def make_shared_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "Pilot#" + "".join(secrets.choice(alphabet) for _ in range(10))


def get_credentials() -> dict[str, str]:
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    values = parse_env_file(CREDENTIALS_FILE)
    shared = values.get("PILOT_SHARED_PASSWORD", "").strip()
    if not shared:
        shared = make_shared_password()
        CREDENTIALS_FILE.write_text(
            "# Локальный файл. Не добавлять в Git и не отправлять публично.\n"
            f"PILOT_SHARED_PASSWORD={shared}\n",
            encoding="utf-8",
        )
        print(f"  Создан локальный файл паролей: {CREDENTIALS_FILE}")
    if shared.startswith("замените_"):
        raise RuntimeError(
            "В pilot_credentials.env остался пароль-заглушка. "
            "Укажите реальный временный пароль или удалите файл для автогенерации."
        )
    if len(shared) < 8:
        raise RuntimeError("PILOT_SHARED_PASSWORD должен быть не короче 8 символов.")
    return {login: values.get(f"PASSWORD_{login.upper()}", shared) for login, _, _ in EXPECTED_USERS}


def make_password_hash(password: str, iterations: int = 260000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def generate_password_sql(credentials: dict[str, str]) -> str:
    hashes = {login: make_password_hash(password) for login, password in credentials.items()}
    lines = [
        "SET client_encoding = 'UTF8';",
        "",
        "-- Создать/обновить пилотного администратора. Остальные связи не меняются.",
        "INSERT INTO users (login, password_hash, role, doctor_id, patient_id)",
        "VALUES (" + ", ".join([
            sql_literal("admin26_08"),
            sql_literal(hashes["admin26_08"]),
            sql_literal("admin"),
            "NULL",
            "NULL",
        ]) + ")",
        "ON CONFLICT (login) DO UPDATE SET",
        "    password_hash = EXCLUDED.password_hash,",
        "    role = 'admin',",
        "    doctor_id = NULL,",
        "    patient_id = NULL;",
        "",
    ]
    for login, role, _ in EXPECTED_USERS:
        if login == "admin26_08":
            continue
        lines.extend([
            "DO $mis$",
            "DECLARE v_rows INTEGER;",
            "BEGIN",
            "    UPDATE users",
            f"       SET password_hash = {sql_literal(hashes[login])}",
            f"     WHERE login = {sql_literal(login)}",
            f"       AND role = {sql_literal(role)};",
            "    GET DIAGNOSTICS v_rows = ROW_COUNT;",
            "    IF v_rows <> 1 THEN",
            f"        RAISE EXCEPTION 'Не удалось обновить пароль {login}: строк %', v_rows;",
            "    END IF;",
            "END",
            "$mis$;",
            "",
        ])
    lines.extend([
        "-- Контроль врачебных привязок после смены только password_hash.",
        "DO $mis$",
        "BEGIN",
        "    IF EXISTS (",
        "        SELECT 1 FROM users",
        "        WHERE role IN ('doctor', 'department_head', 'chief_physician')",
        "          AND doctor_id IS NULL",
        "          AND login IN ('zakharova_m','kazarkin_d','vozova_a','lobanova_n','kuznetsova_t')",
        "    ) THEN",
        "        RAISE EXCEPTION 'У врачебной учётной записи отсутствует doctor_id';",
        "    END IF;",
        "END",
        "$mis$;",
        "",
    ])
    return "\n".join(lines)


def generate_guide(credentials: dict[str, str], app_version: str) -> str:
    role_rows = []
    for login, _, description in EXPECTED_USERS:
        role_rows.append(
            "<tr>"
            f"<td>{html.escape(description)}</td>"
            f"<td><code>{html.escape(login)}</code></td>"
            f"<td><code>{html.escape(credentials[login])}</code></td>"
            "</tr>"
        )
    rows_html = "\n".join(role_rows)
    return f"""<!doctype html>
<html lang=\"ru\">
<head>
<meta charset=\"utf-8\">
<title>Памятка тестировщика МИС</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; max-width: 980px; margin: 32px auto; line-height: 1.45; color: #202124; }}
h1, h2 {{ color: #17365d; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0 28px; }}
th, td {{ border: 1px solid #b8c2cc; padding: 9px 12px; text-align: left; }}
th {{ background: #eef3f8; }}
code {{ font-size: 1.05em; }}
.warning {{ padding: 12px 16px; background: #fff4ce; border-left: 5px solid #d6a100; }}
.good {{ padding: 12px 16px; background: #e8f5e9; border-left: 5px solid #2e7d32; }}
</style>
</head>
<body>
<h1>МИС Нефрология — пилотное тестирование</h1>
<p>Версия сборки: <strong>{html.escape(app_version)}</strong></p>
<div class=\"good\"><strong>Запуск:</strong> дважды нажмите ярлык «МИС Нефрология». Программа работает только локально по адресу <code>http://127.0.0.1:8000/login</code>.</div>
<h2>Учётные записи</h2>
<table>
<thead><tr><th>Роль / сотрудник</th><th>Логин</th><th>Временный пароль</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>
<p>Логины, роли и привязки к врачам сохранены. Установщик изменяет только хеши временных паролей; расписание и карточки приёмов остаются связанными через <code>doctor_id</code>.</p>
<h2>Что проверить</h2>
<ol>
<li>Вход под каждой ролью и доступность соответствующих разделов.</li>
<li>Поиск пациента и открытие архивного приёма.</li>
<li>Скачивание исходного архивного документа и формирование Word.</li>
<li>Создание нового пациента, первичного и повторного приёма.</li>
<li>Ввод анализов, расчёты, диагнозы, рекомендации и группы назначений.</li>
<li>Расписание врача и переход из записи расписания в карточку приёма.</li>
<li>Повторное открытие данных после перезапуска компьютера.</li>
</ol>
<h2>Как передать результаты разработчику</h2>
<p>Откройте меню «Пуск» → «МИС Нефрология — пилот» → <strong>«Выгрузить данные тестирования»</strong>. В папке «Документы\\MIS_Pilot_Exports» появится ZIP с полным снимком PostgreSQL, журналами и контрольной информацией.</p>
<div class=\"warning\"><strong>Важно:</strong> установщик и выгрузки содержат медицинские данные. Не отправляйте их обычной почтой и не загружайте в публичные облака. Используйте защищённый носитель или согласованный закрытый канал.</div>
<h2>Остановка</h2>
<p>Обычно ничего останавливать не требуется. При необходимости используйте пункт «Остановить МИС Нефрология» в меню «Пуск».</p>
</body>
</html>
"""


def get_git_version() -> str:
    try:
        result = run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture=True,
        )
        commit = (result.stdout or "").strip()
    except Exception:
        commit = "no-git"
    return f"pilot-{dt.datetime.now():%Y.%m.%d}-{commit}"


def clean_work() -> dict[str, Path]:
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT_DIR.glob("MIS_Nephrology_Pilot_Setup*.exe"):
        old.unlink()
    paths = {
        "staging": WORK_DIR / "staging",
        "payload": WORK_DIR / "staging" / "payload",
        "postgres": WORK_DIR / "staging" / "postgres",
        "runtime_dist": WORK_DIR / "staging" / "runtime",
        "pyi_work": WORK_DIR / "pyinstaller-work",
        "pyi_dist": WORK_DIR / "pyinstaller-dist",
        "build_venv": WORK_DIR / "build-venv",
        "inno": WORK_DIR / "inno",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def copy_postgres_runtime(pg_bin: Path, destination: Path) -> None:
    pg_root = pg_bin.parent
    for name in ("bin", "lib", "share"):
        source = pg_root / name
        if not source.is_dir():
            raise RuntimeError(f"В PostgreSQL отсутствует каталог {source}")
        shutil.copytree(source, destination / name, dirs_exist_ok=True)
    print(f"  PostgreSQL runtime скопирован из {pg_root}")


def create_backup(pg_bin: Path, project_env: dict[str, str], destination: Path) -> None:
    command = [
        str(pg_bin / "pg_dump.exe"),
        "--host", project_env.get("DB_HOST", "127.0.0.1"),
        "--port", project_env.get("DB_PORT", "5432"),
        "--username", project_env["DB_USER"],
        "--dbname", project_env["DB_NAME"],
        "--format=custom",
        "--compress=6",
        "--no-owner",
        "--no-privileges",
        "--file", str(destination),
    ]
    run(command, env=pg_env(project_env))
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("pg_dump не создал снимок базы.")
    print(f"  Снимок базы: {destination.stat().st_size / 1024 / 1024:.1f} МБ")


def download_vc_redist(destination: Path) -> None:
    local_override = PRIVATE_DIR / "vc_redist.x64.exe"
    if local_override.is_file():
        shutil.copy2(local_override, destination)
        return
    print(f"  Скачивание {VC_REDIST_URL}")
    urllib.request.urlretrieve(VC_REDIST_URL, destination)
    if destination.stat().st_size < 1_000_000:
        raise RuntimeError("Скачанный vc_redist.x64.exe выглядит повреждённым.")


def build_venv_python(venv_dir: Path) -> Path:
    venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
    python = venv_dir / "Scripts" / "python.exe"
    run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    run([
        str(python), "-m", "pip", "install",
        "-r", str(PROJECT_ROOT / "requirements.txt"),
        f"pyinstaller=={PYINSTALLER_VERSION}",
    ])
    run([
        str(python),
        "-c",
        (
            "import itsdangerous; "
            "from starlette.middleware.sessions import SessionMiddleware; "
            "print('Session dependency check: OK')"
        ),
    ])
    return python


def project_app_modules() -> list[str]:
    modules: list[str] = []
    for path in sorted((PROJECT_ROOT / "app").rglob("*.py")):
        relative = path.relative_to(PROJECT_ROOT).with_suffix("")
        parts = list(relative.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            modules.append(".".join(parts))
    return sorted(set(modules))


def generate_spec(destination: Path, runtime_script: Path) -> None:
    project = str(PROJECT_ROOT)
    script = str(runtime_script)
    app_modules = project_app_modules()
    content = f'''# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

PROJECT_ROOT = {project!r}
hiddenimports = {app_modules!r} + collect_submodules("uvicorn") + collect_submodules("itsdangerous")
datas = [
    (PROJECT_ROOT + r"\\app", "app"),
]
for package in ("fastapi", "starlette", "uvicorn", "itsdangerous", "python-docx", "psycopg2-binary"):
    try:
        datas += copy_metadata(package)
    except Exception:
        pass

a = Analysis(
    [{script!r}],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=["pytest", "playwright"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MIS_Nephrology_Runtime",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MIS_Nephrology_Runtime",
)
'''
    destination.write_text(content, encoding="utf-8")


def build_runtime(build_python: Path, paths: dict[str, Path]) -> Path:
    spec = WORK_DIR / "MIS_Nephrology_Runtime.spec"
    generate_spec(spec, RUNTIME_SOURCE)
    run([
        str(build_python), "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath", str(paths["pyi_dist"]),
        "--workpath", str(paths["pyi_work"]),
        str(spec),
    ], cwd=PROJECT_ROOT)
    source = paths["pyi_dist"] / "MIS_Nephrology_Runtime"
    if not (source / "MIS_Nephrology_Runtime.exe").is_file():
        raise RuntimeError("PyInstaller не создал MIS_Nephrology_Runtime.exe.")
    shutil.copytree(source, paths["runtime_dist"], dirs_exist_ok=True)
    return paths["runtime_dist"]


def find_iscc(explicit: str | None, *, allow_install: bool = True) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    found = shutil.which("ISCC.exe") or shutil.which("iscc")
    if found:
        candidates.append(Path(found))
    for env_name in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(env_name)
        if base:
            candidates.extend([
                Path(base) / "Inno Setup 6" / "ISCC.exe",
                Path(base) / "Programs" / "Inno Setup 6" / "ISCC.exe",
            ])
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    winget = shutil.which("winget")
    if winget and allow_install:
        print("  Inno Setup не найден. Устанавливаю через winget...")
        run([
            winget, "install", "--id", "JRSoftware.InnoSetup", "-e", "--silent",
            "--accept-package-agreements", "--accept-source-agreements",
        ])
        return find_iscc(explicit=None, allow_install=False)
    raise RuntimeError(
        "Не найден Inno Setup 6 и winget. Установите Inno Setup 6, затем повторите сборку."
    )


def inno_quote_path(path: Path) -> str:
    return str(path.resolve())


def render_iss(paths: dict[str, Path], app_version: str) -> Path:
    template = ISS_TEMPLATE.read_text(encoding="utf-8")
    rendered = (
        template.replace("__APP_VERSION__", app_version)
        .replace("__RUNTIME_SOURCE__", inno_quote_path(paths["runtime_dist"]))
        .replace("__POSTGRES_SOURCE__", inno_quote_path(paths["postgres"]))
        .replace("__PAYLOAD_SOURCE__", inno_quote_path(paths["payload"]))
        .replace("__OUTPUT_DIR__", inno_quote_path(OUTPUT_DIR))
    )
    destination = paths["inno"] / "MIS_Nephrology_Pilot.iss"
    destination.write_text(rendered, encoding="utf-8-sig")
    return destination


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_tests(skip: bool) -> None:
    if skip:
        print("  Тесты пропущены по --skip-tests.")
        return
    env = os.environ.copy()
    env.pop("RUN_DB_LAYER_TESTS", None)
    env.pop("RUN_BROWSER_TESTS", None)
    run([sys.executable, "-m", "pytest", "-q"], cwd=PROJECT_ROOT, env=env)


def build(args: argparse.Namespace) -> Path:
    require_windows()
    project_env = validate_project()
    app_version = get_git_version()

    print_step(1, "Проверка тестов проекта")
    run_tests(args.skip_tests)

    print_step(2, "Проверка PostgreSQL, базы и учётных записей")
    pg_bin = find_postgres_bin(args.postgres_bin)
    verify_source_database(pg_bin, project_env)

    print_step(3, "Проверка исходных архивных документов")
    archive_root = get_archive_root(args, project_env)
    archive_count = verify_archive_files(pg_bin, project_env, archive_root)

    print_step(4, "Подготовка временных тестовых паролей")
    credentials = get_credentials()
    print(f"  Пароли сохранены локально: {CREDENTIALS_FILE}")

    print_step(5, "Подготовка снимка базы и установочных данных")
    paths = clean_work()
    create_backup(pg_bin, project_env, paths["payload"] / "pilot_database.backup")
    (paths["payload"] / "pilot_passwords.sql").write_text(
        generate_password_sql(credentials), encoding="utf-8"
    )
    (paths["payload"] / "Памятка_тестировщика_МИС.html").write_text(
        generate_guide(credentials, app_version), encoding="utf-8"
    )
    print("  Копирование медицинского архива...")
    shutil.copytree(archive_root, paths["payload"] / "medical_archive", dirs_exist_ok=True)
    copy_postgres_runtime(pg_bin, paths["postgres"])
    download_vc_redist(paths["payload"] / "vc_redist.x64.exe")

    payload_size = sum(path.stat().st_size for path in paths["payload"].rglob("*") if path.is_file())
    print(f"  Размер медицинского payload: {payload_size / 1024 / 1024 / 1024:.2f} ГБ")
    if payload_size > 3_500_000_000:
        print("  ВНИМАНИЕ: payload больше 3.5 ГБ; сборка одного EXE может занять много времени.")

    print_step(6, "Создание автономного Windows runtime")
    build_python = build_venv_python(paths["build_venv"])
    build_runtime(build_python, paths)

    print_step(7, "Сборка единого EXE через Inno Setup")
    iscc = find_iscc(args.iscc)
    iss = render_iss(paths, app_version)
    run([str(iscc), str(iss)])

    setup = OUTPUT_DIR / "MIS_Nephrology_Pilot_Setup.exe"
    if not setup.is_file():
        raise RuntimeError("Inno Setup не создал итоговый EXE.")

    manifest = {
        "built_at": dt.datetime.now().isoformat(timespec="seconds"),
        "version": app_version,
        "source_database": project_env["DB_NAME"],
        "postgres_source_version": "18.x",
        "archive_root": str(archive_root),
        "archive_documents_verified": archive_count,
        "setup_file": setup.name,
        "setup_size_bytes": setup.stat().st_size,
        "setup_sha256": sha256(setup),
        "local_app_url": "http://127.0.0.1:8000/login",
        "local_postgres_port": 55432,
    }
    (OUTPUT_DIR / "build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    shutil.copy2(
        paths["payload"] / "Памятка_тестировщика_МИС.html",
        OUTPUT_DIR / "Памятка_тестировщика_МИС.html",
    )

    print("\nСБОРКА ГОТОВА")
    print(f"Установщик: {setup}")
    print(f"SHA-256: {manifest['setup_sha256']}")
    print(f"Памятка с логинами и паролями: {OUTPUT_DIR / 'Памятка_тестировщика_МИС.html'}")
    return setup


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Сборка автономного установщика пилотной МИС Нефрология"
    )
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--archive-root")
    parser.add_argument("--postgres-bin")
    parser.add_argument("--iscc")
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        build(args)
        return 0
    except KeyboardInterrupt:
        print("\nСборка отменена.", file=sys.stderr)
        return 130
    except Exception as exc:
        print("\nОШИБКА СБОРКИ", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        print(f"Рабочая папка: {WORK_DIR}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
