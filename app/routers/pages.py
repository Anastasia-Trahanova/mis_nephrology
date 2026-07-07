"""
Назначение файла: compatibility-заглушка после разделения pages.py.

Что выполняет файл:
- оставляет импорт app.routers.pages безопасным для старого кода;
- не содержит маршрутов;
- новые HTML-страницы лежат в home.py, patient_pages.py и appointment_pages.py;
- экспорт лежит в exports.py;
- лабораторные API лежат в lab_api.py.

Что редактировать:
- новые маршруты добавлять не сюда, а в тематические роутеры.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["pages_compat"])
