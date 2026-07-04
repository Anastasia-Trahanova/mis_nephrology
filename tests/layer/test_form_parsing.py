"""
Что тестируется:
- технический разбор HTML-формы в app/services/form_parsing.py;
- пустые строки -> None;
- числа с запятой -> формат для БД;
- списки значений из формы;
- безопасный доступ к элементам списка;
- выбор даты анализа или даты приёма по умолчанию.

Зачем:
эти функции используются почти во всех разделах формы приёма. Если они сломаются,
пустые значения начнут сохраняться как мусор, а табличные анализы могут начать
съезжать по колонкам.
"""

from __future__ import annotations

from datetime import date

from app.services.form_parsing import (
    date_at,
    empty_to_none,
    get_form_list_keep_empty,
    get_numeric_list,
    get_text_list,
    has_any_indexed_value,
    join_form_values,
    max_list_length,
    numeric_to_db,
    parse_bool,
    parse_date_or_default,
    value_at,
)

from .factories import FakeForm


def test_empty_to_none_strips_empty_values():
    assert empty_to_none(None) is None
    assert empty_to_none("") is None
    assert empty_to_none("   ") is None
    assert empty_to_none("  текст  ") == "текст"


def test_numeric_to_db_normalizes_numbers_for_postgres():
    assert numeric_to_db("3,6") == "3.6"
    assert numeric_to_db(" 1 234,5 ") == "1234.5"
    assert numeric_to_db("") is None


def test_parse_bool_supports_html_checkbox_values():
    assert parse_bool("true") is True
    assert parse_bool("1") is True
    assert parse_bool("yes") is True
    assert parse_bool("on") is True
    assert parse_bool(None) is False
    assert parse_bool("false") is False


def test_join_form_values_combines_checkboxes_and_other_field():
    assert join_form_values(["голени", "стопы"], "лицо") == "голени, стопы, лицо"
    assert join_form_values(["", "  "], "") is None


def test_get_lists_keep_order_and_empty_columns():
    form = FakeForm(
        {
            "hemoglobin": ["130", "", "125,5"],
            "comment": ["одно", "", "три"],
        }
    )

    assert get_numeric_list(form, "hemoglobin") == ["130", None, "125.5"]
    assert get_text_list(form, "comment") == ["одно", None, "три"]
    assert get_form_list_keep_empty(form, "comment") == ["одно", None, "три"]


def test_value_at_and_indexed_value_helpers():
    assert value_at(["a"], 0) == "a"
    assert value_at(["a"], 1) is None
    assert value_at(["a"], 1, default="x") == "x"

    assert has_any_indexed_value([[None, "130"], [None, None]], 0) is False
    assert has_any_indexed_value([[None, "130"], [None, None]], 1) is True


def test_date_helpers_use_default_date_when_empty():
    default = date(2026, 7, 4)

    assert date_at([""], 0, default) == default
    assert date_at(["2026-07-03"], 0, default) == "2026-07-03"

    assert parse_date_or_default("", default) == default
    assert parse_date_or_default("2026-07-03", default) == date(2026, 7, 3)


def test_max_list_length_handles_empty_inputs():
    assert max_list_length() == 0
    assert max_list_length([1], [1, 2, 3], []) == 3
