"""
Тесты расчета клиренса креатинина по формуле Cockcroft–Gault.
Этот файл проверяет расчет СКФ по формуле Кокрофта-Голта.

Входные значения
----------------
- креатинин крови: мкмоль/л;
- возраст: полных лет;
- масса тела: кг;
- пол пациента.

Внутри функции креатинин переводится мкмоль/л -> mg/dL через деление на 88.4.

Что проверяют тесты
-------------------
1. Контрольный расчет для мужчины.
2. Контрольный расчет для женщины.
3. Применение коэффициента 0.85 для женщин.
4. Поддержку старого формата пола:
   - False — женский пол;
   - True — мужской пол.
5. Возврат None при некорректных данных:
   - пустой или нулевой креатинин;
   - отсутствующий возраст;
   - отсутствующая или нулевая масса тела;
   - отсутствующий пол.

Cockcroft–Gault может использоваться для оценки СКФ и дозировок.
Результат зависит от единиц измерения креатинина, возраста, массы и пола, поэтому эти параметры обязательно проверяются отдельно.
"""


import pytest

from app.medical_algorithms.cockcroft_gault import calculate_cockcroft_gault


@pytest.mark.parametrize(
    ("creatinine_umol_l", "age", "weight_kg", "gender", "expected_crcl"),
    [
        # Креатинин 88.4 мкмоль/л = 1.0 mg/dL
        # Мужчина: ((140 - 60) * 70) / (72 * 1.0) = 77.78 мл/мин
        (88.4, 60, 70, "Мужской", 77.78),

        # Женщина: результат мужчины * 0.85 = 66.11 мл/мин
        (88.4, 60, 70, "Женский", 66.11),
    ],
)
def test_calculate_cockcroft_gault_reference_values(
    creatinine_umol_l,
    age,
    weight_kg,
    gender,
    expected_crcl,
):
    assert calculate_cockcroft_gault(creatinine_umol_l, age, weight_kg, gender) == expected_crcl


def test_calculate_cockcroft_gault_accepts_boolean_gender_from_old_project():
    female_result = calculate_cockcroft_gault(88.4, 60, 70, False)
    male_result = calculate_cockcroft_gault(88.4, 60, 70, True)

    assert female_result == 66.11
    assert male_result == 77.78


@pytest.mark.parametrize(
    ("creatinine_umol_l", "age", "weight_kg", "gender"),
    [
        (None, 60, 70, "Мужской"),
        ("", 60, 70, "Мужской"),
        (0, 60, 70, "Мужской"),
        (-1, 60, 70, "Мужской"),
        (88.4, None, 70, "Мужской"),
        (88.4, 0, 70, "Мужской"),
        (88.4, -1, 70, "Мужской"),
        (88.4, 60, None, "Мужской"),
        (88.4, 60, 0, "Мужской"),
        (88.4, 60, -1, "Мужской"),
        (88.4, 60, 70, None),
    ],
)
def test_calculate_cockcroft_gault_invalid_inputs_return_none(
    creatinine_umol_l,
    age,
    weight_kg,
    gender,
):
    assert calculate_cockcroft_gault(creatinine_umol_l, age, weight_kg, gender) is None
