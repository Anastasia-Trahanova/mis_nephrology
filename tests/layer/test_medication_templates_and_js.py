"""Контрактные тесты HTML/Jinja и JavaScript модуля лекарств."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.medication_therapy import MEDICATION_THERAPY_GROUPS, build_medication_therapy_groups


ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app" / "templates"
JS_FILE = ROOT / "app" / "static" / "js" / "medication_therapy.js"


def _environment() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)


def test_form_renders_five_independent_groups_with_own_datalists():
    dictionary = [
        {"display_name": name}
        for group in MEDICATION_THERAPY_GROUPS
        for name in group["medications"]
    ]
    prefilled = [
        {
            "therapy_group": "Нефропротекция",
            "medication": "Финеренон",
            "dosage": "10 мг",
            "schedule": "1 раз в день",
        }
    ]
    groups = build_medication_therapy_groups(dictionary, prefilled)

    html = _environment().get_template("appointment_form/_medications.html").render(
        medication_therapy_groups=groups
    )

    assert html.count('class="card mb-3 medication-therapy-group"') == 5
    assert html.count('class="medication-row-template"') == 5
    assert html.count("add-medication-row-btn") == 5
    for group in groups:
        assert f'id="medications-{group["code"]}"' in html
        assert f'data-medication-group="{group["value"]}"' in html
        assert f'value="{group["value"]}"' in html
        for suggestion in group["suggestions"]:
            assert f'value="{suggestion}"' in html

    assert 'value="Финеренон"' in html
    assert 'value="10 мг"' in html
    assert 'value="1 раз в день"' in html


def test_form_keeps_free_text_input_and_group_hidden_field():
    source = (TEMPLATES / "appointment_form" / "_medications.html").read_text(encoding="utf-8")

    assert 'type="hidden" name="therapy_group"' in source
    assert 'type="text"' in source
    assert 'name="medication"' in source
    assert 'list="medications-{{ group.code }}"' in source
    assert "required" not in source


def test_medication_script_is_connected_once():
    medications_source = (TEMPLATES / "appointment_form" / "_medications.html").read_text(encoding="utf-8")
    scripts_source = (TEMPLATES / "appointment_form" / "_scripts.html").read_text(encoding="utf-8")

    assert (medications_source + scripts_source).count("/static/js/medication_therapy.js") == 1


def test_javascript_supports_add_remove_clear_and_select_on_focus():
    source = JS_FILE.read_text(encoding="utf-8")

    assert "medicationTherapyInitialized" in source
    assert "input[name=\"medication\"], input[name=\"dosage\"], input[name=\"schedule\"]" in source
    assert "field.select();" in source
    assert "template.content.cloneNode(true)" in source
    assert "rows.length === 1" in source
    assert "clearMedicationRow(row)" in source
    assert "row.remove();" in source
    assert "input.value = '';" in source


def test_patient_card_shows_only_nonempty_groups_and_bolds_only_drug_name():
    groups = build_medication_therapy_groups(
        prescriptions=[
            {
                "therapy_group": "Коррекция АД, ЧСС",
                "medication": "Лозартан",
                "dosage": "50 мг",
                "schedule": "утром",
            },
            {
                "therapy_group": "Другие препараты",
                "medication": "Препарат вручную",
                "dosage": None,
                "schedule": None,
            },
        ]
    )

    html = _environment().get_template("patient_card/_prescriptions.html").render(
        medication_therapy_groups=groups,
        diet_info=None,
    )

    assert "Препараты для коррекции АД, ЧСС" in html
    assert "Дополнительно" in html
    assert "Нефропротекторные препараты" not in html
    assert "<strong>Лозартан</strong>" in html
    assert "<strong>Препарат вручную</strong>" in html
    assert "50 мг" in html and "(утром)" in html
