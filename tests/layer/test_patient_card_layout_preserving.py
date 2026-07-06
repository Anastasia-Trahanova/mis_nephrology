"""
Тесты layout-preserving разбиения карточки пациента.

Что тестируется:
- patient_card.html больше не является большим монолитом, а подключает partial-шаблоны;
- partial-шаблоны имеют описание назначения в начале файла;
- сохранена исходная ключевая структура страницы:
  ФИО сверху, слева история приёмов, справа карточка выбранного приёма;
- сохранены исходные места кнопок «Добавить приём» и «Скачать Word»;
- шаблон рендерится на фейковых данных и показывает основные медицинские блоки.

Зачем:
Этот тест нужен, чтобы техническое дробление patient_card.html не превращалось
в незаметное изменение дизайна. После будущих правок можно быстро проверить,
что каркас карточки пациента не был случайно перестроен.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape


TEMPLATES_DIR = Path("app/templates")
PARTIALS_DIR = TEMPLATES_DIR / "patient_card"

EXPECTED_PARTIALS = [
    "_header.html",
    "_appointments_sidebar.html",
    "_visit_card_header.html",
    "_visit_summary.html",
    "_patient_brief.html",
    "_survey.html",
    "_examination.html",
    "_cbc_history.html",
    "_biochemistry_history.html",
    "_metrics_history.html",
    "_urinalysis_history.html",
    "_albuminuria_history.html",
    "_ultrasound_history.html",
    "_ckd_prognosis.html",
    "_diagnoses.html",
    "_prescriptions.html",
    "_export_buttons.html",
]


def ns(**kwargs):
    return SimpleNamespace(**kwargs)


def _env() -> Environment:
    return Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"base.html": "{% block content %}{% endblock %}"}),
                FileSystemLoader(str(TEMPLATES_DIR)),
            ]
        ),
        autoescape=select_autoescape(["html", "xml"]),
    )


def _context() -> dict:
    appointment_date = datetime(2026, 7, 4, 10, 30)
    investigation_date = date(2026, 7, 3)

    patient = ns(
        id=101,
        last_name="Тестова",
        first_name="Пациентка",
        patronymic="Карточковна",
        birth_date=date(1980, 1, 15),
        gender_str="женский",
    )

    selected = ns(
        id=202,
        appointment_date=appointment_date,
        doctor_name="Лобанова Н.",
        location_name="Нефрология",
        branch_name="Филиал 1",
        age_at_appointment=46,
        life_anamnesis="Анамнез жизни",
        disease_anamnesis="Анамнез заболевания",
        complaints="Жалобы",
        heredity=True,
        heredity_description="Наследственность отягощена",
        comorbidities="АГ",
        skin_condition="обычные",
        edema_location="голени",
        systolic_pressure=130,
        diastolic_pressure=80,
        bp_note="самоконтроль",
        heart_rate=72,
        height=170,
        weight=70,
        bmi=24.22,
        main_diagnosis="Хроническая болезнь почек",
        complications="Нет",
        diag_comorbidities="АГ",
    )

    return {
        "patient": patient,
        "appointments": [
            ns(appointment_id=202, appointment_date=appointment_date, doctor_name="Лобанова Н."),
        ],
        "selected_appointment": selected,
        "cbc_history": [
            ns(
                investigation_date=investigation_date,
                hemoglobin=130,
                erythrocytes=4.5,
                leukocytes=6.1,
                platelets=250,
                esr=10,
                mcv=88,
                hematocrit=39,
            )
        ],
        "biochemistry_history": [
            ns(
                investigation_date=investigation_date,
                creatinine=100,
                urea=6.2,
                uric_acid=320,
                glucose=5.1,
                total_protein=70,
                albumin=42,
                potassium=4.3,
                calcium=2.3,
                phosphorus=1.1,
                ferritin=90,
                ptg=45,
            )
        ],
        "metrics_history": [
            ns(
                investigation_date=investigation_date,
                egfr_ckdepi=65.4,
                crcl_cockcroft_gault=72.1,
                ckd_stage="С2",
            )
        ],
        "urinalysis_history": [
            ns(
                investigation_date=investigation_date,
                specific_gravity="1.015",
                protein=0.1,
                leukocytes=2,
                erythrocytes=1,
                bacteria=0,
            )
        ],
        "albuminuria_history": [
            ns(
                investigation_date=investigation_date,
                urine_albumin=30,
                urine_albumin_unit="mg_l",
                urine_creatinine=10,
                urine_creatinine_unit="mmol_l",
                albumin_creatinine_ratio=3,
                albuminuria_category="A2",
            )
        ],
        "ultrasound_history": [
            ns(
                investigation_date=investigation_date,
                left_kidney_size="110x55",
                right_kidney_size="108x54",
                left_parenchyma=16,
                right_parenchyma=15,
                description="УЗИ без особенностей",
            )
        ],
        "ckd_prognosis_history": [
            ns(
                assessment_date=investigation_date,
                gfr_category="С2",
                albuminuria_category="A2",
                combined_category="С2/A2",
                prognosis_level="moderate",
                prognosis_text="умеренный риск",
            )
        ],
        "ckd_prognosis_current": ns(
            assessment_date=investigation_date,
            combined_category="С2/A2",
            prognosis_level="moderate",
            prognosis_text="умеренный риск",
        ),
        "icd10_diagnoses": [
            ns(diagnosis_type="main", icd10_diagnosis="N18.2 ХБП 2 стадии", doctor_note="уточнение"),
        ],
        "diet_info": ns(
            diet="Ограничение соли",
            recommendations="Контроль креатинина и ACR",
            next_control_date=date(2026, 10, 4),
        ),
        "medications": [ns(medication="Лозартан", dosage="50 мг", schedule="1 раз в день")],
    }


def test_patient_card_includes_all_expected_partials():
    source = (TEMPLATES_DIR / "patient_card.html").read_text(encoding="utf-8")

    for partial in EXPECTED_PARTIALS:
        assert f'{{% include "patient_card/{partial}" %}}' in source


def test_patient_card_keeps_original_layout_markers():
    source = (TEMPLATES_DIR / "patient_card.html").read_text(encoding="utf-8")
    sidebar = (PARTIALS_DIR / "_appointments_sidebar.html").read_text(encoding="utf-8")
    visit_header = (PARTIALS_DIR / "_visit_card_header.html").read_text(encoding="utf-8")
    export_buttons = (PARTIALS_DIR / "_export_buttons.html").read_text(encoding="utf-8")

    assert '<div class="row mb-4">' in (PARTIALS_DIR / "_header.html").read_text(encoding="utf-8")
    assert 'class="col-md-3"' in source
    assert 'class="col-md-9"' in source
    assert 'id="printContent"' in source

    assert 'card-header bg-primary text-white' in sidebar
    assert 'id="appointmentsList"' in sidebar
    assert 'btn btn-success w-100' in sidebar
    assert '/new-appointment/{{ patient.id }}' in sidebar

    assert 'card-header bg-secondary text-white' in visit_header
    assert 'card-footer' in export_buttons
    assert '/export/{{ selected_appointment.id }}/docx' in export_buttons
    assert 'btn btn-primary' in export_buttons


def test_patient_card_partials_have_description_comments():
    for partial in EXPECTED_PARTIALS:
        text = (PARTIALS_DIR / partial).read_text(encoding="utf-8").lstrip()
        assert text.startswith("{#"), partial
        assert "Назначение файла" in text.split("#}", 1)[0], partial


def test_patient_card_template_renders_medical_blocks_without_changing_layout():
    template = _env().get_template("patient_card.html")
    html = template.render(_context())

    assert "Тестова Пациентка Карточковна" in html
    assert "История приёмов" in html
    assert "➕ Добавить приём" in html
    assert "Приём от 04.07.2026 10:30" in html
    assert "id=\"printContent\"" in html

    assert "Опрос" in html
    assert "Осмотр" in html
    assert "Общий анализ крови" in html
    assert "Биохимический анализ крови" in html
    assert "Расчётные показатели" in html
    assert "Общий анализ мочи" in html
    assert "Альбуминурия по KDIGO" in html
    assert "УЗИ почек" in html
    assert "Матрица риска по KDIGO" in html
    assert "Заключение" in html
    assert "Назначения" in html

    assert "24.22" in html
    assert "1.015" in html
    assert "N18.2 ХБП 2 стадии" in html
    assert "Лозартан" in html
    assert "Скачать Word" in html
