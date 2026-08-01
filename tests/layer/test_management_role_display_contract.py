from pathlib import Path

from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[2]


def test_management_roles_use_doctor_fio_in_login_query():
    source = (ROOT / "app" / "routers" / "auth.py").read_text(encoding="utf-8")

    assert "u.role IN ('doctor', 'chief_physician', 'department_head')" in source
    assert "END AS display_name" in source


def test_management_roles_have_human_readable_labels():
    source = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")

    assert "'chief_physician': 'главный врач'" in source
    assert "'department_head': 'заведующий отделением'" in source
    assert "role_labels.get(current_role, current_role)" in source


def test_management_roles_keep_clinical_navigation():
    source = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")

    assert "clinical_roles = ('doctor', 'chief_physician', 'department_head')" in source
    assert "current_role == 'admin' or current_role in clinical_roles" in source


def test_base_template_compiles():
    env = Environment(loader=FileSystemLoader(ROOT / "app" / "templates"))
    env.get_template("base.html")
