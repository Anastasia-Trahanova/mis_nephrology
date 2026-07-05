"""
Назначение файла: точечно подключить live-проверку форм без ручного поиска мест.

Скрипт делает только безопасные правки:
1. подключает app/static/js/simple_form_guard.js в base.html, если его там нет;
2. подключает app/static/css/02_clinical_messages.css в base.html, если его там нет;
3. убирает серверную блокировку частично заполненной ACR-пары, потому что врач
   сам видит поля формулы в таблице;
4. приводит несколько серверных fallback-сообщений к короткому тексту.

Скрипт можно запускать повторно: он не должен дублировать подключения.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def patch_base_html() -> None:
    path = ROOT / "app" / "templates" / "base.html"
    if not path.exists():
        print("base.html не найден, пропускаю подключение CSS/JS")
        return

    content = read(path)

    css_line = "<link rel=\"stylesheet\" href=\"{{ url_for('static', path='css/02_clinical_messages.css') }}\">"
    if "css/02_clinical_messages.css" not in content:
        if "</head>" in content:
            content = content.replace("</head>", f"    {css_line}\n</head>")
        else:
            content = css_line + "\n" + content

    js_line = "<script src=\"{{ url_for('static', path='js/simple_form_guard.js') }}\"></script>"
    if "js/simple_form_guard.js" not in content:
        if "</body>" in content:
            content = content.replace("</body>", f"    {js_line}\n</body>")
        else:
            content = content + "\n" + js_line + "\n"

    write(path, content)
    print("base.html: CSS/JS подключены")


def patch_validation_py() -> None:
    path = ROOT / "app" / "validation.py"
    if not path.exists():
        print("validation.py не найден, пропускаю")
        return

    content = read(path)

    # Частично заполненная ACR-пара больше не должна блокировать сохранение.
    acr_pattern = re.compile(
        r"\n\s*#\s*Для ACR нужны обе части:.*?\n\s*return errors",
        flags=re.DOTALL,
    )
    if acr_pattern.search(content):
        content = acr_pattern.sub("\n\n    return errors", content)

    # Если остались старые точечные сообщения, делаем их короткими.
    replacements = {
        "Для расчёта ACR нужен креатинин мочи.": "Неверное значение",
        "Для расчёта ACR нужен альбумин мочи.": "Неверное значение",
        "Дата следующего контроля не должна быть раньше даты приёма.": "Дата следующего визита не может быть раньше даты приёма",
        "Некорректная дата исследования.": "Некорректная дата",
        "Поле должно быть числом. ": "",
        "Поле должно быть числом.\n": "",
    }
    for old, new in replacements.items():
        content = content.replace(old, new)

    write(path, content)
    print("validation.py: fallback-сообщения упрощены, ACR-пара не блокируется")


def main() -> None:
    patch_base_html()
    patch_validation_py()
    print("Готово. Перезапустите сервер и обновите страницу через Ctrl+F5.")


if __name__ == "__main__":
    main()
