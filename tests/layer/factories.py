"""
Тестовые фабрики для слоя пациентов и приёмов.

Зачем нужен файл:
- имитировать HTML-форму FastAPI/Starlette без запуска сервера;
- быстро собирать реалистичные данные приёма;
- не дублировать большие словари в каждом тесте.

FakeForm реализует методы form.get(...) и form.getlist(...), которые используются
в сервисах парсинга формы.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any


class FakeForm:
    """Минимальная замена FormData для unit-тестов."""

    def __init__(self, data: dict[str, Any] | None = None):
        self._data: dict[str, list[Any]] = defaultdict(list)
        for key, value in (data or {}).items():
            if isinstance(value, list):
                self._data[key].extend(value)
            else:
                self._data[key].append(value)

    def get(self, key: str, default: Any = None) -> Any:
        values = self._data.get(key)
        if not values:
            return default
        return values[0]

    def getlist(self, key: str) -> list[Any]:
        return list(self._data.get(key, []))


class FakeCursor:
    """
    Fake cursor для проверки SQL-контрактов repository-функций.

    Сохраняет все вызовы execute(query, params). fetchone() возвращает заранее
    заданный словарь.
    """

    def __init__(self, fetchone_result: dict[str, Any] | None = None):
        self.calls: list[tuple[str, Any]] = []
        self.fetchone_result = fetchone_result or {"id": 1}

    def execute(self, query: str, params: Any = None) -> None:
        self.calls.append((query, params))

    def fetchone(self) -> dict[str, Any] | None:
        return self.fetchone_result

    @property
    def last_query(self) -> str:
        return self.calls[-1][0]

    @property
    def last_params(self) -> Any:
        return self.calls[-1][1]


def full_form_data() -> dict[str, Any]:
    """
    Реалистичная форма нового пациента/приёма.

    Включает поля пациента, приёма, чекбоксы, осмотр, анализы, альбуминурию,
    диагнозы, диету, рекомендации и лекарства.
    """
    return {
        "last_name": "Тестова",
        "first_name": "Пациентка",
        "patronymic": "Автотестовна",
        "birth_date": "1980-01-15",
        "gender": "true",
        "phone": "+7 900 000-00-00",
        "doctor_id": "1",
        "location_id": "1",
        "appointment_date": "2026-07-04",
        "appointment_time": "10:30",
        "complaints": "Жалобы из автотеста",
        "education_and_professional_history": "Высшее образование, бухгалтер",
        "housing_conditions": "Жилищные условия удовлетворительные",
        "past_diseases": "ОРВИ, аппендэктомия",
        "habitual_intoxications": "Не курит, алкоголь редко",
        "gynecological_history": "Менопауза с 50 лет",
        "heredity": "true",
        "heredity_description": "Наследственность отягощена по артериальной гипертензии",
        "family_life": "Замужем, двое детей",
        "allergological_history": "Аллергии не отмечает",
        "epidemiological_history": "Контакты с инфекционными больными отрицает",
        "insurance_history": "Полис ОМС действующий",
        "disease_onset": "Заболевание началось около пяти лет назад",
        "disease_course": "Течение волнообразное, наблюдается у нефролога",
        "general_condition": "moderate",
        "consciousness": "clear",
        "bed_position": "forced",
        "bed_position_details": "Полусидя из-за одышки",
        "body_build": "Правильное",
        "constitution_type": "normosthenic",
        "skin_and_mucous_membranes": "Кожа бледная, сухая, слизистые чистые",
        "edema_peripheral": ["голени"],
        "edema_peripheral_other": "стопы",
        "edema_serositis": ["нет"],
        "edema_other": "к вечеру усиливаются",
        "lymph_nodes": "Не увеличены",
        "thyroid_gland": "Не увеличена",
        "musculoskeletal_system": "Без видимой патологии",
        "body_temperature": "36,6",
        "systolic_pressure": "130",
        "diastolic_pressure": "80",
        "bp_note": "сидя",
        "heart_rate": "72",
        "height": "170",
        "weight": "70",
        "veins_condition": "Вены нижних конечностей без особенностей",
        "lung_auscultation": "Дыхание везикулярное",
        "abdomen": "Мягкий, безболезненный",
        "kidney_palpation": "palpable",
        "kidney_palpation_details": "Правая почка пальпируется в положении стоя",
        "pasternatsky_result": "negative",
        "pasternatsky_side": "bilateral",
        "cbc_investigation_date": ["2026-07-03", ""],
        "hemoglobin": ["130", ""],
        "erythrocytes": ["4.5", ""],
        "leukocytes": ["6.1", ""],
        "platelets": ["250", ""],
        "esr": ["10", ""],
        "mcv": ["88", ""],
        "hematocrit": ["39", ""],
        "biochemistry_investigation_date": ["2026-07-03", ""],
        "creatinine": ["100", ""],
        "urea": ["6.2", ""],
        "uric_acid": ["320", ""],
        "glucose": ["5.1", ""],
        "total_protein": ["70", ""],
        "albumin": ["42", ""],
        "potassium": ["4.3", ""],
        "calcium": ["2.3", ""],
        "phosphorus": ["1.1", ""],
        "ferritin": ["90", ""],
        "ptg": ["45", ""],
        "urinalysis_investigation_date": ["2026-07-03", ""],
        "specific_gravity": ["1015", ""],
        "urine_protein": ["0.1", ""],
        "urine_leukocytes": ["2", ""],
        "urine_erythrocytes": ["1", ""],
        "bacteria": ["0", ""],
        "albuminuria_investigation_date": ["2026-07-03", ""],
        "urine_albumin": ["30", ""],
        "urine_albumin_unit": ["mg_l", "mg_l"],
        "urine_creatinine": ["10", ""],
        "urine_creatinine_unit": ["mmol_l", "mmol_l"],
        "ultrasound_investigation_date": ["2026-07-03", ""],
        "left_kidney_size": ["110x55", ""],
        "right_kidney_size": ["108x54", ""],
        "left_parenchyma": ["16", ""],
        "right_parenchyma": ["15", ""],
        "ultrasound_desc": ["Без расширения ЧЛС", ""],
        "main_diagnosis": "Хроническая болезнь почек",
        "complications": "Нет",
        "comorbidities_diag": "Гипертоническая болезнь",
        "icd10_main_diagnosis": "",
        "icd10_main_note": "",
        "icd10_complication_diagnosis": [""],
        "icd10_complication_note": [""],
        "icd10_comorbidity_diagnosis": [""],
        "icd10_comorbidity_note": [""],
        "diet": "Ограничение соли",
        "next_control_date": "2026-10-04",
        "recommendations": "Контроль креатинина и ACR",
        "medication": ["Лозартан", ""],
        "dosage": ["50 мг", ""],
        "schedule": ["1 раз в день", ""],
    }


def full_fake_form() -> FakeForm:
    return FakeForm(full_form_data())


def minimal_appointment_data() -> dict[str, Any]:
    """Структурированный словарь как результат parse_appointment_form(...)."""
    from app.services.appointment_form_parser import parse_appointment_form

    return parse_appointment_form(
        full_fake_form(),
        datetime(2026, 7, 4, 10, 30),
    )
