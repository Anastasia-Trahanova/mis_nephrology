"""
Тесты frontend-слоя live-валидации.

Эти тесты не запускают браузер. Они проверяют, что в проекте есть файлы,
которые нужны для поведения формы:
- короткие сообщения;
- проверка дат;
- проверка числовых клинических полей;
- подсветка конкретного поля;
- запрет отправки формы при ошибке.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_live_validation_js_contains_short_messages_and_field_rules():
    content = (ROOT / "app" / "static" / "js" / "simple_form_guard.js").read_text(encoding="utf-8")

    assert "Не все обязательные поля заполнены" in content
    assert "Неверное значение" in content
    assert "Дата рождения не может быть в будущем" in content
    assert "Дата приёма не может быть раньше даты рождения" in content
    assert "Дата следующего визита не может быть раньше даты приёма" in content
    assert "Дата следующего визита не может быть раньше текущей даты" in content
    assert "Дата исследования не может быть позже даты приёма" in content

    assert "systolic_pressure" in content
    assert "diastolic_pressure" in content
    assert "specific_gravity" in content
    assert "creatinine" in content
    assert "urine_albumin" in content
    assert "urine_creatinine" in content


def test_live_validation_js_prevents_bad_submit_and_focuses_field():
    content = (ROOT / "app" / "static" / "js" / "simple_form_guard.js").read_text(encoding="utf-8")

    assert "addEventListener(\"submit\"" in content
    assert "event.preventDefault()" in content
    assert "scrollIntoView" in content
    assert ".focus" in content
    assert "mis-field-invalid" in content
    assert "mis-field-error-message" in content


def test_clinical_messages_css_styles_field_errors():
    content = (ROOT / "app" / "static" / "css" / "02_clinical_messages.css").read_text(encoding="utf-8")

    assert ".mis-field-invalid" in content
    assert ".mis-field-error-message" in content
    assert ".mis-form-error-summary" in content
    assert "--mis-error-border-color" in content


def test_clinical_validation_partial_is_short_fallback():
    content = (ROOT / "app" / "templates" / "_clinical_validation.html").read_text(encoding="utf-8")

    assert "validation_errors" in content
    assert "Неверное значение" in content
    assert "диапазон" not in content.lower()
