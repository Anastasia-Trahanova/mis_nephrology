@echo off
REM Быстрые безопасные тесты слоя patients/services/repositories.
REM Не пишут в БД и не требуют запущенного приложения.

pytest tests\layer
