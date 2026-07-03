"""
Тест переходного мостика `app/calculations.py`.
Этот файл проверяет, что старый импорт из `app.calculations` продолжает работать после выноса медицинских алгоритмов в папку: app/medical_algorithms/

То есть старый код может по-прежнему писать:
    from app.calculations import calculate_all_metrics
    from app.calculations import calculate_ckd_prognosis
а реальные функции уже берутся из новых отдельных модулей.

Что проверяют тесты
-------------------
1. Что из `app.calculations` импортируются старые имена функций.
2. Что CKD-EPI считается через мостик.
3. Что нормализация стадии работает через мостик:
   - G3b -> С3б.
4. Что прогноз KDIGO работает через мостик:
   - C4 + A3 -> very_high.
5. Что общий расчет показателей работает через мостик.

Зачем это важно
---------------
Это защита от поломки старого кода во время постепенного рефакторинга.
Мы не обязаны сразу менять все импорты в `database.py`, роутерах и других файлах.
Пока есть мостик, старый код продолжает работать.
"""

def test_calculations_bridge_exports_old_function_names():
    from app.calculations import (
        calculate_all_metrics,
        calculate_ckd_prognosis,
        calculate_ckd_epi_2021,
        normalize_ckd_stage_for_storage,
    )

    assert calculate_ckd_epi_2021(88.4, 50, "Женский") == 68.63
    assert normalize_ckd_stage_for_storage("G3b") == "С3б"

    prognosis = calculate_ckd_prognosis("C4", "A3")
    assert prognosis["level"] == "very_high"
    assert prognosis["gfr_category"] == "С4"

    metrics = calculate_all_metrics(
        creatinine_umol_l=88.4,
        birth_date="1980-01-01",
        appointment_date="2026-01-01",
        gender="Женский",
        weight_kg=70,
    )
    assert metrics["ckd_stage"] == "С2"
