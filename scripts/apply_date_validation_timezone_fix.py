"""
Назначение файла: точечно исправляет frontend-проверку дат в simple_form_guard.js.

Проблема:
старый parseIsoDate создавал дату через new Date("YYYY-MM-DDT00:00:00")
и затем сравнивал через toISOString(). В часовом поясе UTC+ это могло сдвигать
дату на предыдущий день и помечать нормальную дату приёма как «Некорректная дата».

Что делает скрипт:
заменяет parseIsoDate на проверку по компонентам год/месяц/день без UTC-сдвига.
Остальной JS не трогает.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "app" / "static" / "js" / "simple_form_guard.js"

NEW_FUNCTION = '''function parseIsoDate(value) {
        const text = String(value || "").trim();

        if (!text) return null;

        const match = text.match(/^(\\d{4})-(\\d{2})-(\\d{2})$/);

        if (!match) return "invalid";

        const year = Number(match[1]);
        const month = Number(match[2]);
        const day = Number(match[3]);

        if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) {
            return "invalid";
        }

        const date = new Date(year, month - 1, day);

        if (Number.isNaN(date.getTime())) return "invalid";

        if (
            date.getFullYear() !== year ||
            date.getMonth() !== month - 1 ||
            date.getDate() !== day
        ) {
            return "invalid";
        }

        return text;
    }'''

PATTERN = re.compile(
    r"function\s+parseIsoDate\s*\(\s*value\s*\)\s*\{.*?return\s+iso\s*===\s*text\s*\?\s*text\s*:\s*\"invalid\"\s*;\s*\}",
    re.DOTALL,
)


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"ERROR: файл не найден: {TARGET}")

    content = TARGET.read_text(encoding="utf-8")

    if "date.toISOString().slice(0, 10)" not in content and "date.getFullYear() !== year" in content:
        print("OK: parseIsoDate уже исправлен, повторная правка не нужна.")
        return

    new_content, count = PATTERN.subn(lambda match: NEW_FUNCTION, content, count=1)

    if count != 1:
        raise SystemExit(
            "ERROR: не удалось автоматически найти старую функцию parseIsoDate. "
            "Открой app/static/js/simple_form_guard.js и замени parseIsoDate вручную из README."
        )

    TARGET.write_text(new_content, encoding="utf-8")
    print("OK: parseIsoDate исправлен без UTC-сдвига дат.")


if __name__ == "__main__":
    main()
