from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest

from app.db.connection import get_db_connection


_ACTIVE_SERVER_LOGS: deque[str] | None = None


def _row_value(row, key, index=0):
    if isinstance(row, dict):
        return row[key]
    try:
        return row[key]
    except (TypeError, KeyError):
        return row[index]


def _current_database_name() -> str:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database() AS name")
            row = cur.fetchone()
    return str(_row_value(row, "name", 0))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _server_is_ready(url: str) -> bool:
    try:
        with urlopen(f"{url}/login", timeout=0.5) as response:
            return int(getattr(response, "status", 200)) < 500
    except HTTPError as error:
        return error.code < 500
    except (URLError, TimeoutError, OSError):
        return False


@pytest.fixture(scope="session", autouse=True)
def browser_base_url():
    """Start an isolated FastAPI process on the same TEST DB as pytest.

    Browser tests no longer depend on a separately started server on port 8000.
    This prevents accidental production-DB testing and DB/server mismatches.
    """
    if os.getenv("RUN_BROWSER_TESTS") != "1":
        pytest.skip("Set RUN_BROWSER_TESTS=1 to run browser tests.")

    db_name = _current_database_name()
    if "test" not in db_name.lower():
        pytest.fail(
            f"Refusing to start browser tests against database {db_name!r}. "
            "Use a dedicated database whose name contains 'test'."
        )

    repo_root = Path(__file__).resolve().parents[2]
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["DB_NAME"] = db_name
    env["APP_BASE_URL"] = base_url
    # Ensure the subprocess accepts the loopback host even if the local .env is stricter.
    allowed_hosts = env.get("ALLOWED_HOSTS", "")
    allowed = [item.strip() for item in allowed_hosts.split(",") if item.strip()]
    for required in ("127.0.0.1", "localhost", "testserver"):
        if required not in allowed:
            allowed.append(required)
    env["ALLOWED_HOSTS"] = ",".join(allowed)

    global _ACTIVE_SERVER_LOGS
    logs: deque[str] = deque(maxlen=200)
    _ACTIVE_SERVER_LOGS = logs
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    def _drain_output():
        if process.stdout is None:
            return
        for line in process.stdout:
            logs.append(line.rstrip())

    reader = threading.Thread(target=_drain_output, daemon=True)
    reader.start()

    old_base_url = os.environ.get("APP_BASE_URL")
    os.environ["APP_BASE_URL"] = base_url

    try:
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(
                    "The isolated FastAPI process exited during browser-test startup.\n"
                    + "\n".join(logs)
                )
            if _server_is_ready(base_url):
                break
            time.sleep(0.1)
        else:
            pytest.fail(
                f"FastAPI did not become ready at {base_url}.\n" + "\n".join(logs)
            )

        yield base_url
    finally:
        if old_base_url is None:
            os.environ.pop("APP_BASE_URL", None)
        else:
            os.environ["APP_BASE_URL"] = old_base_url

        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        _ACTIVE_SERVER_LOGS = None


@pytest.fixture
def browser_server_logs(browser_base_url):
    """Return a snapshot function for the isolated FastAPI process output."""
    def _snapshot() -> list[str]:
        return list(_ACTIVE_SERVER_LOGS or [])
    return _snapshot


@pytest.fixture
def page(browser_base_url):
    """Local Playwright page fixture; pytest-playwright plugin is not required."""
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=os.getenv("E2E_HEADLESS", "1") != "0")
        context = browser.new_context()
        page = context.new_page()
        try:
            yield page
        finally:
            context.close()
            browser.close()
