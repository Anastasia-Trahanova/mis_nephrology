"""
Общие настройки pytest для всех тестов.

Этот файл не содержит медицинских тестов. Он нужен технически, чтобы pytest стабильно видел папку `app` при запуске тестов из корня проекта.
Без этого на некоторых компьютерах может возникать ошибка импорта:
    ModuleNotFoundError: No module named 'app'
"""

from pathlib import Path
import sys


# Чтобы pytest стабильно видел пакет app при запуске из корня проекта.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
