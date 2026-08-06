from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_filter_enter_is_global_and_loaded_from_base():
    base = read("app/templates/base.html")
    script = read("app/static/js/filter_form_hotkeys.js")

    assert "js/filter_form_hotkeys.js" in base
    assert "В формах фильтров: применить фильтры" in base
    assert 'method !== "get"' in script
    assert "form.requestSubmit" in script
    assert 'event.stopImmediatePropagation()' in script


def test_global_enter_does_not_submit_post_forms_or_textareas():
    script = read("app/static/js/filter_form_hotkeys.js")

    assert 'CONTROL_SELECTOR = "input, select"' in script
    assert 'method !== "get"' in script
    assert 'dataset.enterSubmit === "false"' in script


def test_analytics_does_not_duplicate_enter_handler():
    script = read("app/static/js/management_analytics.js")

    assert 'code === "Enter"' not in script
    assert "function applyLocation" in script
    assert "form.requestSubmit();" in script
    assert 'code === "KeyS"' in script
