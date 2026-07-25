"""Единое формирование полного названия места приёма."""
from __future__ import annotations

from typing import Any, Mapping


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip(" ,")


def build_location_full_name(source: Mapping[str, Any] | None) -> str:
    """Собирает организацию, филиал, отделение и адрес без пустых частей."""
    if not source:
        return ""

    parts: list[str] = []
    seen: set[str] = set()
    for value in (
        source.get("company_name"),
        source.get("branch_name"),
        source.get("location_name") or source.get("name"),
        source.get("factual_address") or source.get("location_address"),
    ):
        part = _clean(value)
        key = part.casefold()
        if part and key not in seen:
            parts.append(part)
            seen.add(key)

    return ", ".join(parts)
