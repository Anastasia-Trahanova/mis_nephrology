from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_sidebar_replaces_top_navigation_and_has_home_link():
    base = read("app/templates/base.html")
    assert 'id="appSidebar"' in base
    assert 'href="/" title="Главная"' in base
    assert '<span class="app-brand"' in base
    assert 'navbar-brand' not in base


def test_sidebar_preserves_role_based_links():
    base = read("app/templates/base.html")
    assert "management_roles = ('admin', 'chief_physician', 'department_head')" in base
    assert 'href="/analytics"' in base
    assert 'href="/ckd-registry"' in base
    assert "current_role == 'admin'" in base
    assert 'href="/admin/audit"' in base


def test_sidebar_assets_and_mobile_controls_are_connected():
    base = read("app/templates/base.html")
    css = read("app/static/css/10_sidebar.css")
    js = read("app/static/js/sidebar.js")
    assert "css/10_sidebar.css" in base
    assert "js/sidebar.js" in base
    assert "sidebar-mobile-open" in css
    assert "misSidebarCollapsed" in js
    assert "sidebarBackdrop" in base and "sidebarBackdrop" in js


def test_sidebar_keeps_original_width_wraps_long_labels_and_shows_version():
    base = read("app/templates/base.html")
    css = read("app/static/css/10_sidebar.css")

    assert "Версия 1.0.0" in base
    assert "--app-sidebar-width: 232px" in css
    assert "white-space: normal" in css
    assert "overflow-wrap: break-word" in css
    assert ".sidebar-collapsed .app-sidebar__meta { display: none; }" in css
