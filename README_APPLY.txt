1. Распаковать архив в корень проекта с заменой файлов.
2. Выполнить:

   python apply_management_role_ui_fix.py
   python -m pytest -q tests\layer\test_management_role_access_contract.py
   python -m pytest -q --ignore=tests\browser

После этого chief_physician и department_head имеют клинические права врача,
доступ к расписанию и спискам пациентов. Журнал аудита остаётся только для admin.
