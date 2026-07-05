"""
Назначение файла: проверяет, что frontend-парсер дат не использует UTC-сдвиг.

Почему это важно:
input type="date" отдаёт дату в формате YYYY-MM-DD. Если затем создать Date и
сравнить через toISOString(), в часовом поясе UTC+ дата может стать предыдущим
днём и валидная дата приёма ошибочно подсветится как «Некорректная дата».
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_simple_form_guard_parse_iso_date_does_not_use_utc_iso_shift():
    content = (ROOT / "app" / "static" / "js" / "simple_form_guard.js").read_text(encoding="utf-8")

    assert "function parseIsoDate(value)" in content
    assert "date.toISOString().slice(0, 10)" not in content
    assert "date.getFullYear() !== year" in content
    assert "date.getMonth() !== month - 1" in content
    assert "date.getDate() !== day" in content
