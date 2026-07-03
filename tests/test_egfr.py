"""
Тесты расчета eGFR по формуле CKD-EPI 2021 creatinine.
Этот файл проверяет функцию расчета расчетной скорости клубочковой фильтрации по формуле CKD-EPI 2021 creatinine.

Входные значения
----------------
- креатинин крови: мкмоль/л;
- возраст: полных лет;
- пол пациента: старый формат проекта или строка.

Внутри функции креатинин переводится мкмоль/л -> mg/dL через деление на 88.4.

Что проверяют тесты
-------------------
1. Расчет на нескольких контрольных примерах.
2. Поддержку старого формата пола:
   - False — женский пол;
   - True — мужской пол.
3. Возврат None при некорректных данных:
   - пустой креатинин;
   - нулевой или отрицательный креатинин;
   - отсутствующий возраст;
   - нулевой или отрицательный возраст;
   - отсутствующий пол.

Зачем это важно
---------------
CKD-EPI — один из ключевых медицинских расчетов системы. Эти тесты фиксируют, что формула не изменилась случайно после рефакторинга.

"""

import pytest

from app.medical_algorithms.egfr import calculate_ckd_epi_2021


@pytest.mark.parametrize(
    ("creatinine_umol_l", "age", "gender", "expected_egfr"),
    [
        # Креатинин 88.4 мкмоль/л = 1.0 mg/dL
        (88.4, 50, "Женский", 68.63),

        # Креатинин 106.08 мкмоль/л = 1.2 mg/dL
        (106.08, 60, "Мужской", 69.23),

        # Креатинин 70.72 мкмоль/л = 0.8 mg/dL
        (70.72, 70, "Женский", 79.22),
    ],
)
def test_calculate_ckd_epi_2021_reference_values(
    creatinine_umol_l,
    age,
    gender,
    expected_egfr,
):
    assert calculate_ckd_epi_2021(creatinine_umol_l, age, gender) == expected_egfr


def test_calculate_ckd_epi_2021_accepts_boolean_gender_from_old_project():
    female_result = calculate_ckd_epi_2021(88.4, 50, False)
    male_result = calculate_ckd_epi_2021(88.4, 50, True)

    # В старом проекте False используется как женский пол,
    # True — как мужской. Проверяем, что это поведение сохранено.
    assert female_result == 68.63
    assert male_result == 91.69


@pytest.mark.parametrize(
    ("creatinine_umol_l", "age", "gender"),
    [
        (None, 50, "Женский"),
        ("", 50, "Женский"),
        (0, 50, "Женский"),
        (-1, 50, "Женский"),
        (88.4, None, "Женский"),
        (88.4, 0, "Женский"),
        (88.4, -1, "Женский"),
        (88.4, 50, None),
    ],
)
def test_calculate_ckd_epi_2021_invalid_inputs_return_none(
    creatinine_umol_l,
    age,
    gender,
):
    assert calculate_ckd_epi_2021(creatinine_umol_l, age, gender) is None
