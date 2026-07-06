"""
Одноразовый фикс после внедрения KDIGO-матрицы.

Зачем нужен:
Jinja воспринимает выражение `cell.items` не как поле словаря `"items"`,
а как встроенный метод dict.items. Поэтому шаблон падает с ошибкой:
TypeError: 'builtin_function_or_method' object is not iterable.

Что делает:
- заменяет обращение `cell.items` в шаблоне матрицы KDIGO
  на безопасное словарное обращение `cell["items"]`;
- не трогает базу данных, миграции, SQL и медицинскую логику.

После успешного запуска, тестов и проверки страницы этот скрипт можно удалить.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "patient_card" / "_ckd_prognosis.html"


REPLACEMENTS = {
    "{% for item in cell.items %}": '{% for item in cell["items"] %}',
    "{{ cell.items|length }}": '{{ cell["items"]|length }}',
    "{% if cell.items %}": '{% if cell["items"] %}',
    "{% if cell.items|length %}": '{% if cell["items"]|length %}',
}


def main() -> None:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Не найден шаблон: {TEMPLATE_PATH}")

    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    original = text

    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)

    if text == original:
        print("OK: шаблон уже исправлен, замен не потребовалось.")
        return

    TEMPLATE_PATH.write_text(text, encoding="utf-8")
    print(f"OK: исправлен Jinja-шаблон KDIGO-матрицы: {TEMPLATE_PATH}")


if __name__ == "__main__":
    main()
