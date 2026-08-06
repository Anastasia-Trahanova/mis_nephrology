from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_audit_page_exposes_hotkey_targets():
    template = (ROOT / "app" / "templates" / "admin" / "audit.html").read_text(encoding="utf-8")

    assert 'id="auditPage"' in template
    assert 'id="auditFiltersForm"' in template
    assert 'id="auditResetFilters"' in template
    assert 'id="auditCsvForm"' in template
    assert 'data-audit-event-row' in template
    assert 'data-audit-open' in template
    assert 'data-audit-page="previous"' in template
    assert 'data-audit-page="next"' in template
    assert "js/audit_hotkeys.js" in template


def test_audit_hotkeys_cover_page_actions():
    script = (ROOT / "app" / "static" / "js" / "audit_hotkeys.js").read_text(encoding="utf-8")

    assert 'code === "Enter" && inFilters' in script
    assert 'code === "KeyS"' in script
    assert 'code === "KeyR"' in script
    assert 'code === "KeyC"' in script
    assert 'code === "KeyO"' in script
    assert 'code === "ArrowLeft" || code === "ArrowRight"' in script
    assert 'code === "ArrowUp" || code === "ArrowDown"' in script
    assert "requestSubmit()" in script


def test_hotkeys_help_describes_audit_page():
    template = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")

    assert "is_audit_page = current_path == '/admin/audit'" in template
    assert "{% elif is_audit_page %}Журнал аудита" in template
    assert "В формах фильтров: применить фильтры" in template
    assert "Открыть выбранное событие" in template
