"""
Конфигурация pytest для тестов слоя patients/services/repositories.

Здесь регистрируются marker-ы, чтобы pytest не ругался на custom markers,
если в проекте пока нет общего pytest.ini.
"""

from __future__ import annotations


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "db_layer: optional tests that write to the development/test database",
    )
    config.addinivalue_line(
        "markers",
        "browser: optional tests that require a running app and Playwright",
    )
