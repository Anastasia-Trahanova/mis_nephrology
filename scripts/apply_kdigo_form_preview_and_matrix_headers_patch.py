"""
Одноразовый скрипт подключения KDIGO-preview к форме и проверки матрицы.

Зачем нужен:
- если предыдущий KDIGO-патч распакован, но live-блок не появился в форме,
  этот скрипт принудительно вставляет include в блок «Заключение»;
- добавляет CSS KDIGO в base.html, если ссылка ещё не была подключена;
- не трогает миграции, таблицы БД, медицинские расчёты и сохранённые данные.

Что можно удалить:
- после запуска, зелёных тестов и коммита этот скрипт можно удалить.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def patch_conclusion_template() -> bool:
    path = "app/templates/appointment_form/_conclusion.html"
    content = read(path)
    include_line = '{% include "appointment_form/_kdigo_risk_preview.html" %}'

    if include_line in content:
        return False

    # Самый частый случай: осталась старая текстовая заглушка.
    if "Прогноз ХБП по KDIGO:" in content:
        content = content.replace("Прогноз ХБП по KDIGO:", include_line, 1)
        write(path, content)
        return True

    # Если заглушку уже удалили, вставляем preview перед диагнозами.
    diagnosis_marker = '{% include "icd10_diagnosis_block.html" %}'
    if diagnosis_marker in content:
        content = content.replace(diagnosis_marker, include_line + "\n\n" + diagnosis_marker, 1)
        write(path, content)
        return True

    # Последний вариант: вставка сразу после заголовка «Заключение».
    heading_marker = "##### Заключение"
    if heading_marker in content:
        content = content.replace(heading_marker, heading_marker + "\n\n" + include_line, 1)
        write(path, content)
        return True

    raise RuntimeError("Не найдено место для вставки KDIGO-preview в _conclusion.html")


def patch_base_css() -> bool:
    path = "app/templates/base.html"
    content = read(path)
    link = '<link rel="stylesheet" href="{{ url_for(\'static\', path=\'css/04_kdigo_risk.css\') }}">'

    if "css/04_kdigo_risk.css" in content:
        return False

    if "</head>" in content:
        content = content.replace("</head>", f"    {link}\n</head>", 1)
        write(path, content)
        return True

    marker = "{% block content %}"
    if marker in content:
        content = content.replace(marker, f"{link}\n{marker}", 1)
        write(path, content)
        return True

    raise RuntimeError("Не найдено место для подключения css/04_kdigo_risk.css в base.html")


def main() -> None:
    changed_conclusion = patch_conclusion_template()
    changed_css = patch_base_css()

    print("OK: KDIGO preview подключён к форме приёма.")
    print(f"_conclusion.html изменён: {'да' if changed_conclusion else 'нет, уже было'}")
    print(f"base.html изменён: {'да' if changed_css else 'нет, уже было'}")
    print("Теперь запусти: pytest tests/layer")


if __name__ == "__main__":
    main()
