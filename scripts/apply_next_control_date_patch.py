"""
Назначение файла: точечный патч для даты следующего контроля в форме нового приёма.

Что делает:
- находит поле name="next_control_date" в app/templates/appointment_form/_conclusion.html;
- убирает автоподстановку даты из прошлого приёма / прошлой диеты;
- оставляет поле пустым для нового сохраняемого приёма;
- убирает required у этого поля, если он случайно был добавлен.

Почему так:
дата последнего приёма должна быть только статичным текстом сверху формы
«В форму подгружены данные последнего приёма (...)».
Она не должна превращаться в дату следующего контроля нового приёма и не должна
участвовать в блокирующих проверках новой формы.

Запускать из корня проекта:
    python scripts\apply_next_control_date_patch.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "app" / "templates" / "appointment_form" / "_conclusion.html"


def _patch_next_control_date_input(content: str) -> tuple[str, bool]:
    """Возвращает обновлённый шаблон и признак, была ли сделана замена."""

    # Ищем именно input, внутри которого есть name="next_control_date".
    # DOTALL нужен, потому что атрибуты input обычно разбиты на несколько строк.
    pattern = re.compile(
        r"<input\b(?=[^>]*\bname\s*=\s*(['\"])next_control_date\1)[^>]*>",
        re.IGNORECASE | re.DOTALL,
    )

    def replace_input(match: re.Match[str]) -> str:
        tag = match.group(0)

        # Дата следующего контроля не должна быть обязательной.
        tag = re.sub(r"\s+required\b", "", tag, flags=re.IGNORECASE)

        # Убираем любую старую автоподстановку value="{{ ... }}" / value='...'.
        if re.search(r"\svalue\s*=", tag, flags=re.IGNORECASE):
            tag = re.sub(
                r"\svalue\s*=\s*(['\"])(?:(?!\1).)*\1",
                ' value=""',
                tag,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            )
        else:
            # Если value не было, добавляем пустое значение перед закрытием input.
            tag = tag[:-1].rstrip() + ' value="">'

        # Добавляем понятный комментарий только один раз, перед полем.
        comment = (
            "{# Дата следующего контроля относится к НОВОМУ приёму. "
            "Не подставляем сюда дату из прошлого приёма/диеты: она остаётся "
            "только историческим текстом в верхнем сообщении формы. #}\n"
        )

        if "Дата следующего контроля относится к НОВОМУ приёму" in content:
            return tag

        return comment + tag

    new_content, count = pattern.subn(replace_input, content, count=1)
    return new_content, count > 0


def main() -> None:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Не найден файл: {TEMPLATE_PATH}")

    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    new_content, changed = _patch_next_control_date_input(content)

    if not changed:
        raise RuntimeError(
            "Не удалось найти <input ... name=\"next_control_date\" ...> "
            "в app/templates/appointment_form/_conclusion.html. "
            "Пришли этот файл, и я подстрою патч под фактическую разметку."
        )

    TEMPLATE_PATH.write_text(new_content, encoding="utf-8")
    print("OK: поле next_control_date теперь не подставляет дату из прошлого приёма.")


if __name__ == "__main__":
    main()
