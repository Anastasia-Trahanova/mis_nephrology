@echo off
REM Интеграционный тест реальной dev/test БД.
REM ВНИМАНИЕ: создаёт тестового пациента и потом пытается удалить его.

set RUN_DB_LAYER_TESTS=1
pytest tests\integration\test_patient_appointment_database_workflow.py
