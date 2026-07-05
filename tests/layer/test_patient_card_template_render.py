"""
Что тестируется:
- новый patient_card.html как каркас карточки пациента;
- все partial-шаблоны app/templates/patient_card/*.html;
- отображение ключевых блоков: шапка, история приёмов, опрос, осмотр,
  анализы, метрики, альбуминурия, диагнозы, назначения и экспорт;
- отображение нормализованного удельного веса мочи 1.015;
- отображение BMI, стадии ХБП, ACR и МКБ-10;
- состояние карточки, когда приём не выбран.

Как тестируется:
Тесты рендерят Jinja-шаблон напрямую через FileSystemLoader.
Настоящий base.html заменяется минимальным тестовым base.html, чтобы проверять
именно карточку пациента и её partial-шаблоны, а не общий layout приложения.

Зачем:
После разделения большого patient_card.html на partial-шаблоны важно иметь
быстрый тест, который можно запускать после любых правок интерфейса карточки.
Тесты не требуют БД, FastAPI-сервера и браузера.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, StrictUndefined


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
PATIENT_CARD_DIR = TEMPLATES_DIR / "patient_card"


def _ns(**kwargs):
    return SimpleNamespace(**kwargs)


def _render_patient_card(**overrides) -> str:
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"base.html": "<!doctype html><html><body>{% block content %}{% endblock %}</body></html>"}),
                FileSystemLoader(str(TEMPLATES_DIR)),
            ]
        ),
        undefined=StrictUndefined,
        autoescape=False,
    )

    context = _patient_card_context()
    context.update(overrides)

    template = env.get_template("patient_card.html")
    return template.render(**context)


def _patient_card_context() -> dict:
    patient = _ns(
        id=101,
        last_name="Тестова",
        first_name="Пациентка",
        patronymic="Карточная",
        birth_date=date(1980, 1, 15),
        age=46,
        gender_str="Женский",
    )

    selected_appointment = _ns(
        id=202,
        appointment_id=202,
        appointment_date=datetime(2026, 7, 4, 10, 30),
        doctor_name="Иванов И.И.",
        location_name="Нефрология",
        branch_name="Главный филиал",
        age_at_appointment=46,
        life_anamnesis="Анамнез жизни тестовый",
        disease_anamnesis="Анамнез заболевания тестовый",
        complaints="Жалобы тестовые",
        heredity=True,
        heredity_description="ХБП у родственников",
        comorbidities="Артериальная гипертензия",
        skin_condition="Обычная окраска, нормальная влажность",
        edema_location="Голени",
        systolic_pressure=130,
        diastolic_pressure=80,
        bp_note="сидя",
        heart_rate=72,
        height=170,
        weight=70,
        bmi=24.22,
        main_diagnosis="Хроническая болезнь почек",
        complications="Нет",
        diag_comorbidities="Артериальная гипертензия",
    )

    appointments = [
        _ns(id=202, appointment_id=202, appointment_date=datetime(2026, 7, 4, 10, 30), doctor_name="Иванов И.И."),
        _ns(id=201, appointment_id=201, appointment_date=datetime(2026, 6, 1, 9, 0), doctor_name="Петров П.П."),
    ]

    return {
        "patient": patient,
        "selected_appointment": selected_appointment,
        "appointments": appointments,
        "cbc_history": [
            _ns(
                investigation_date=date(2026, 7, 3),
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
            _ns(
                investigation_date=date(2026, 7, 3),
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
            _ns(
                investigation_date=date(2026, 7, 3),
                egfr_ckdepi=67.1,
                crcl_cockcroft_gault=73.2,
                ckd_stage="С2",
            )
        ],
        "urinalysis_history": [
            _ns(
                investigation_date=date(2026, 7, 3),
                specific_gravity="1.015",
                protein=0.1,
                leukocytes=2,
                erythrocytes=1,
                bacteria=0,
            )
        ],
        "albuminuria_history": [
            _ns(
                investigation_date=date(2026, 7, 3),
                urine_albumin=30,
                urine_albumin_unit="mg_l",
                urine_creatinine=10,
                urine_creatinine_unit="mmol_l",
                albumin_creatinine_ratio=3.0,
                albuminuria_category="A2",
            )
        ],
        "ultrasound_history": [
            _ns(
                investigation_date=date(2026, 7, 3),
                left_kidney_size="110x55",
                right_kidney_size="108x54",
                left_parenchyma=16,
                right_parenchyma=15,
                description="Без обструкции",
            )
        ],
        "ckd_prognosis_current": _ns(
            assessment_date=date(2026, 7, 3),
            gfr_category="С2",
            albuminuria_category="A2",
            combined_category="С2A2",
            prognosis_level="moderate",
            prognosis_text="Умеренный риск",
        ),
        "ckd_prognosis_history": [
            _ns(
                assessment_date=date(2026, 7, 3),
                gfr_category="С2",
                albuminuria_category="A2",
                combined_category="С2A2",
                prognosis_level="moderate",
                prognosis_text="Умеренный риск",
            )
        ],
        "icd10_diagnoses": [
            _ns(diagnosis_type="main", icd10_diagnosis="N18.2 Хроническая болезнь почек, стадия 2", doctor_note="тест"),
            _ns(diagnosis_type="comorbidity", icd10_diagnosis="I10 Эссенциальная гипертензия", doctor_note=""),
        ],
        "diet_info": _ns(
            diet="Ограничение соли",
            recommendations="Контроль креатинина и ACR",
            next_control_date=date(2026, 10, 4),
        ),
        "medications": [
            _ns(medication="Лозартан", dosage="50 мг", schedule="1 раз в день"),
            _ns(medication="Дапаглифлозин", dosage="10 мг", schedule="1 раз в день"),
        ],
    }


def test_all_patient_card_templates_have_file_descriptions():
    """
    Проверяет, что каждый новый шаблон начинается с описания назначения файла.

    Это не косметика: через год по первому комментарию должно быть понятно,
    зачем нужен partial и что в нём можно безопасно менять.
    """
    files = [TEMPLATES_DIR / "patient_card.html"] + sorted(PATIENT_CARD_DIR.glob("*.html"))

    assert files

    for file_path in files:
        text = file_path.read_text(encoding="utf-8")
        assert "Назначение файла" in text, f"Нет описания назначения файла: {file_path}"


def test_patient_card_renders_selected_appointment_and_core_sections():
    """Проверяет рендер карточки, когда выбран конкретный приём."""
    html = _render_patient_card()

    assert "Тестова" in html
    assert "Пациентка" in html
    assert "Приём от 04.07.2026 10:30" in html

    for section_title in [
        "История приёмов",
        "Опрос",
        "Осмотр",
        "Общий анализ крови",
        "Биохимический анализ крови",
        "Расчётные показатели",
        "Общий анализ мочи",
        "Альбуминурия по KDIGO",
        "УЗИ почек",
        "Прогноз ХБП по KDIGO",
        "Заключение и диагнозы",
        "Диета и рекомендации",
        "Лекарственные назначения",
    ]:
        assert section_title in html


def test_patient_card_renders_key_clinical_values():
    """
    Проверяет ключевые клинические значения после сохранения и нормализации.

    Особенно важно:
    - BMI отображается в карточке;
    - specific_gravity отображается как нормализованное 1.015;
    - стадия ХБП выводится русской С;
    - ACR и категория альбуминурии видны врачу.
    """
    html = _render_patient_card()

    assert "24.22" in html
    assert "1.015" in html
    assert "67.1" in html
    assert "С2" in html
    assert "3.0" in html
    assert "A2" in html
    assert "N18.2" in html
    assert "Лозартан" in html
    assert "Дапаглифлозин" in html


def test_patient_card_renders_export_and_navigation_links():
    """Проверяет ссылки на повторный приём, выбранный приём и Word-экспорт."""
    html = _render_patient_card()

    assert 'href="/new-appointment/101"' in html
    assert 'href="/patient/101?appointment_id=202"' in html
    assert 'href="/export/202/docx"' in html
    assert 'data-testid="docx-export-link"' in html


def test_patient_card_renders_empty_state_when_no_appointment_selected():
    """Проверяет состояние карточки, когда пациент есть, но приём не выбран."""
    html = _render_patient_card(selected_appointment=None)

    assert "Выберите приём из списка слева" in html
    assert "Опрос" not in html
    assert "Общий анализ крови" not in html
