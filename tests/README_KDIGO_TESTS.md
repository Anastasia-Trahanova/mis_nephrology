# KDIGO v7 tests

Архив добавляет новые тесты под текущий интерфейс KDIGO:

- `tests/layer/test_kdigo_v7_medical_matrix_scenarios.py` — 17 сценариев матрицы KDIGO и фраза для сохранения.
- `tests/layer/test_kdigo_v7_form_live_contract.py` — контракт формы: radio-строки, одна нейтральная фраза, история отдельно, подсветка только строк, JS-синтаксис.
- `tests/layer/test_kdigo_v7_repository_pairing.py` — backend-сохранение: построчные пары, uneven 2+1/1+2, одинаковые дата/категория с разными source-id, исключение невыбранной строки, fallback на прошлые анализы, stale-фильтр, сохранение в БД через fake cursor.

Старые KDIGO UI-contract тесты лучше удалить, потому что они проверяют старый интерфейс с матрицей/крестиком/видимым полем заключения.
