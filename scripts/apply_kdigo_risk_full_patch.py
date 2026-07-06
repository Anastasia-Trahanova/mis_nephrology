"""
Одноразовый скрипт применения KDIGO-патча.

Зачем нужен:
- новые файлы из архива распаковываются сразу;
- этот скрипт аккуратно подключает их к уже существующим файлам проекта;
- после успешного запуска, тестов и коммита файл можно удалить.

Что меняет:
- вставляет live-блок KDIGO в app/templates/appointment_form/_conclusion.html;
- добавляет CSS-ссылку в app/templates/base.html;
- добавляет kdigo_excluded_pairs в parser формы;
- передаёт исключённые врачом пары в save_ckd_prognosis_for_appointment();
- добавляет матрицу KDIGO в context карточки пациента.

Что не трогает:
- миграции;
- инструкции по БД;
- структуру таблиц;
- старые анализы пациента.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def patch_conclusion_template() -> None:
    path = "app/templates/appointment_form/_conclusion.html"
    content = read(path)
    include_line = '{% include "appointment_form/_kdigo_risk_preview.html" %}'
    if include_line in content:
        return
    if "Прогноз ХБП по KDIGO:" not in content:
        raise RuntimeError("Не найден текст 'Прогноз ХБП по KDIGO:' в _conclusion.html")
    content = content.replace("Прогноз ХБП по KDIGO:", include_line, 1)
    write(path, content)


def patch_base_css() -> None:
    path = "app/templates/base.html"
    content = read(path)
    link = '<link rel="stylesheet" href="{{ url_for(\'static\', path=\'css/04_kdigo_risk.css\') }}">'
    if "css/04_kdigo_risk.css" in content:
        return
    if "</head>" in content:
        content = content.replace("</head>", f"    {link}\n</head>", 1)
    else:
        # На случай если base.html сильно упрощён: добавляем ссылку перед content-блоком.
        marker = "{% block content %}"
        if marker not in content:
            raise RuntimeError("Не найден </head> или {% block content %} в base.html")
        content = content.replace(marker, f"{link}\n{marker}", 1)
    write(path, content)


def patch_form_parser() -> None:
    path = "app/services/appointment_form_parser.py"
    content = read(path)
    if '"kdigo_excluded_pairs"' in content:
        return
    marker = '"appointment_date_default": appointment_datetime.date(),'
    if marker not in content:
        raise RuntimeError("Не найден appointment_date_default в appointment_form_parser.py")
    content = content.replace(
        marker,
        marker + '\n        "kdigo_excluded_pairs": form.getlist("kdigo_excluded_pair"),',
        1,
    )
    write(path, content)


def patch_save_service() -> None:
    path = "app/services/appointment_save_service.py"
    content = read(path)
    old = "save_ckd_prognosis_for_appointment(appointment_id, cur=cur)"
    new = (
        "save_ckd_prognosis_for_appointment(\n"
        "        appointment_id,\n"
        "        cur=cur,\n"
        "        excluded_pairs=appointment_data.get(\"kdigo_excluded_pairs\", []),\n"
        "    )"
    )
    if "excluded_pairs=appointment_data.get" in content:
        return
    if old not in content:
        raise RuntimeError("Не найден вызов save_ckd_prognosis_for_appointment в appointment_save_service.py")
    content = content.replace(old, new, 1)
    write(path, content)


def patch_patient_card_context_service() -> None:
    path = "app/services/patient_card_context_service.py"
    content = read(path)

    if "build_kdigo_risk_matrix" not in content:
        import_marker = "from app.repositories.patients import _fetch_patient_by_id"
        if import_marker not in content:
            raise RuntimeError("Не найден import_marker в patient_card_context_service.py")
        content = content.replace(
            import_marker,
            "from app.services.kdigo_risk_matrix_service import build_kdigo_risk_matrix\n"
            + import_marker,
            1,
        )

    if "_fetch_appointment_ckd_prognosis_results" not in content:
        content = content.replace(
            "_fetch_appointment_ckd_prognosis,",
            "_fetch_appointment_ckd_prognosis,\n    _fetch_appointment_ckd_prognosis_results,",
            1,
        )

    if "ckd_prognosis_history = _fetch_patient_ckd_prognosis_history" not in content:
        marker = "return {"
        insert = (
            "ckd_prognosis_history = _fetch_patient_ckd_prognosis_history(cur, patient_id, until_date)\n"
            "            ckd_prognosis_matrix = build_kdigo_risk_matrix(ckd_prognosis_history)\n"
            "            ckd_prognosis_current_results = (\n"
            "                _fetch_appointment_ckd_prognosis_results(cur, int(selected_appointment_id))\n"
            "                if selected_appointment_id\n"
            "                else []\n"
            "            )\n"
            "            return {"
        )
        if marker not in content:
            raise RuntimeError("Не найден return { в patient_card_context_service.py")
        content = content.replace(marker, insert, 1)

    content = content.replace(
        '"ckd_prognosis_history": _fetch_patient_ckd_prognosis_history(cur, patient_id, until_date),',
        '"ckd_prognosis_history": ckd_prognosis_history,\n                "ckd_prognosis_matrix": ckd_prognosis_matrix,\n                "ckd_prognosis_current_results": ckd_prognosis_current_results,',
        1,
    )

    write(path, content)


def main() -> None:
    patch_conclusion_template()
    patch_base_css()
    patch_form_parser()
    patch_save_service()
    patch_patient_card_context_service()
    print("OK: KDIGO full patch подключён к проекту.")
    print("Проверь: pytest tests/layer")


if __name__ == "__main__":
    main()
