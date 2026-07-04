from app.medical_algorithms.bmi import calculate_bmi


def test_calculate_bmi_normal_values():
    assert calculate_bmi(170, 70) == 24.22
    assert calculate_bmi(175, 85) == 27.76


def test_calculate_bmi_accepts_strings():
    assert calculate_bmi("170", "70") == 24.22


def test_calculate_bmi_accepts_comma_decimal_separator():
    assert calculate_bmi("170", "70,5") == 24.39


def test_calculate_bmi_empty_values_return_none():
    assert calculate_bmi(None, 70) is None
    assert calculate_bmi(170, None) is None
    assert calculate_bmi("", 70) is None
    assert calculate_bmi(170, "") is None


def test_calculate_bmi_invalid_values_return_none():
    assert calculate_bmi("abc", 70) is None
    assert calculate_bmi(170, "abc") is None


def test_calculate_bmi_zero_or_negative_values_return_none():
    assert calculate_bmi(0, 70) is None
    assert calculate_bmi(-170, 70) is None
    assert calculate_bmi(170, 0) is None
    assert calculate_bmi(170, -70) is None