"""
Тесты объединенного расчета основных показателей приема.
Этот файл проверяет функцию `calculate_all_metrics`, которая объединяет сразу несколько расчетов:

1. возраст пациента на дату приема;
2. eGFR по CKD-EPI 2021;
3. клиренс креатинина по Cockcroft–Gault;
4. категорию СКФ: С1, С2, С3а, С3б, С4, С5.

Входные значения
----------------
- креатинин крови: мкмоль/л;
- дата рождения;
- дата приема;
- пол;
- масса тела, кг.

Что проверяют тесты
-------------------
1. Контрольный полный расчет для пациента.
2. Что функция возвращает ожидаемый словарь:
   - egfr_ckdepi;
   - crcl_cockcroft_gault;
   - ckd_stage.
3. Что при отсутствующем креатинине расчетные значения становятся None.

Зачем это важно
---------------
Эта функция удобна для формы приема: врач вводит исходные данные, а система сразу получает набор расчетных показателей. 
Тест нужен, чтобы проверить связку нескольких алгоритмов, а не только каждую формулу отдельно.
"""

from app.medical_algorithms.metrics import calculate_all_metrics


def test_calculate_all_metrics_reference_female_case():
    result = calculate_all_metrics(
        creatinine_umol_l=88.4,
        birth_date="1980-01-01",
        appointment_date="2026-01-01",
        gender="Женский",
        weight_kg=70,
    )

    assert result == {
        "egfr_ckdepi": 70.36,
        "crcl_cockcroft_gault": 77.68,
        "ckd_stage": "С2",
    }


def test_calculate_all_metrics_missing_values_return_none_fields():
    result = calculate_all_metrics(
        creatinine_umol_l=None,
        birth_date="1980-01-01",
        appointment_date="2026-01-01",
        gender="Женский",
        weight_kg=70,
    )

    assert result["egfr_ckdepi"] is None
    assert result["crcl_cockcroft_gault"] is None
    assert result["ckd_stage"] is None
