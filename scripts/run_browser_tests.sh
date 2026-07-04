#!/usr/bin/env bash
set -euo pipefail
export APP_BASE_URL="${APP_BASE_URL:-http://127.0.0.1:8000}"
export RUN_BROWSER_TESTS=1
pytest tests/browser
