"""Unit-тесты справочника и группировки медикаментозной терапии."""

from __future__ import annotations

from collections import Counter
from types import SimpleNamespace

from app.medication_therapy import (
    DEFAULT_THERAPY_GROUP,
    MEDICATION_THERAPY_GROUPS,
    build_medication_therapy_groups,
    normalize_therapy_group,
)


EXPECTED_GROUPS = (
    (
        "bp_hr",
        "Коррекция АД, ЧСС",
        "Препараты для коррекции АД, ЧСС",
        (
            "Лозартан",
            "Бисопролол",
            "Метопролол",
            "Карведилол",
            "Амлодипин",
            "Лерканидипин",
            "Нифедипин",
            "Нифедипин с модифицированным высвобождением",
            "Спиронолактон",
            "Индапамид",
            "Торасемид",
            "Фуросемид",
            "Моксонидин",
        ),
    ),
    (
        "nephroprotection",
        "Нефропротекция",
        "Нефропротекторные препараты",
        ("Лозартан", "Дапаглифлозин", "Эмпаглифлозин", "Финеренон"),
    ),
    (
        "lipid",
        "Коррекция гиперлипидемии",
        "Препараты для коррекции гиперлипидемии",
        ("Аторвастатин", "Розувастатин", "Питавастатин", "Эзетимиб"),
    ),
    (
        "anemia",
        "Коррекция анемии",
        "Препараты для коррекции анемии",
        (
            "Железа III гидроксид полимальтозат",
            "Железа III гидроксид полисахарозный комплекс",
            "Эпоэтин альфа",
            "Эпоэтин бета",
            "Метоксиполиэтиленгликоль-эпоэтин бета",
        ),
    ),
    (
        "additional",
        "Другие препараты",
        "Дополнительно",
        ("Аллопуринол", "Фебуксостат"),
    ),
)


def test_group_definitions_are_exact_and_stable():
    actual = tuple(
        (group["code"], group["value"], group["title"], group["medications"])
        for group in MEDICATION_THERAPY_GROUPS
    )
    assert actual == EXPECTED_GROUPS
    assert DEFAULT_THERAPY_GROUP == "Другие препараты"


def test_medication_list_contains_27_unique_names_and_only_losartan_is_shared():
    names = [name for group in MEDICATION_THERAPY_GROUPS for name in group["medications"]]
    counts = Counter(names)

    assert len(set(names)) == 27
    assert {name: count for name, count in counts.items() if count > 1} == {
        "Лозартан": 2
    }


def test_normalize_therapy_group_accepts_only_known_russian_values():
    assert normalize_therapy_group("  Нефропротекция  ") == "Нефропротекция"
    assert normalize_therapy_group("Коррекция анемии") == "Коррекция анемии"
    assert normalize_therapy_group(None) == DEFAULT_THERAPY_GROUP
    assert normalize_therapy_group("") == DEFAULT_THERAPY_GROUP
    assert normalize_therapy_group("неизвестная группа") == DEFAULT_THERAPY_GROUP


def test_build_groups_filters_suggestions_by_database_and_preserves_order():
    dictionary = [
        {"display_name": "Финеренон"},
        {"display_name": "Лозартан"},
        {"display_name": "Дапаглифлозин"},
        {"display_name": "Лозартан"},
        {"display_name": "Препарат вне согласованного списка"},
    ]

    groups = build_medication_therapy_groups(dictionary, [])
    by_code = {group["code"]: group for group in groups}

    assert [group["code"] for group in groups] == [item[0] for item in EXPECTED_GROUPS]
    assert by_code["bp_hr"]["suggestions"] == ["Лозартан"]
    assert by_code["nephroprotection"]["suggestions"] == [
        "Лозартан",
        "Дапаглифлозин",
        "Финеренон",
    ]
    assert by_code["lipid"]["suggestions"] == []
    assert all(group["prescriptions"] == [] for group in groups)


def test_build_groups_keeps_manual_drugs_and_moves_unknown_group_to_additional():
    manual = {
        "therapy_group": "Коррекция гиперлипидемии",
        "medication": "Препарат, введённый вручную",
        "dosage": "1 таблетка",
        "schedule": "вечером",
    }
    unknown_group = {
        "therapy_group": "Устаревшая группа",
        "medication": "Другой препарат",
    }
    object_row = SimpleNamespace(
        therapy_group="Коррекция анемии",
        medication="Эпоэтин альфа",
        dosage="4000 МЕ",
        schedule="3 раза в неделю",
    )

    groups = build_medication_therapy_groups(
        medications_dictionary=[],
        prescriptions=[manual, unknown_group, object_row],
    )
    by_value = {group["value"]: group for group in groups}

    assert by_value["Коррекция гиперлипидемии"]["prescriptions"] == [manual]
    assert by_value["Коррекция анемии"]["prescriptions"] == [object_row]
    assert by_value["Другие препараты"]["prescriptions"] == [unknown_group]


def test_build_groups_preserves_order_inside_each_group():
    first = {"therapy_group": "Коррекция АД, ЧСС", "medication": "Лозартан"}
    second = {"therapy_group": "Коррекция АД, ЧСС", "medication": "Амлодипин"}

    groups = build_medication_therapy_groups(prescriptions=[first, second])
    bp_group = next(group for group in groups if group["code"] == "bp_hr")

    assert bp_group["prescriptions"] == [first, second]
