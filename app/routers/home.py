"""
Назначение файла: HTML-роут главной страницы.

Что выполняет файл:
- показывает стартовую страницу со списком фильтров;
- передаёт в шаблон справочники филиалов и врачей;
- не содержит SQL и не формирует документы/экспорт.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.repositories.reference_data import get_branches, get_doctors

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Главная страница приложения."""
    branches = get_branches()
    doctors = get_doctors()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "branches": branches,
            "doctors": doctors,
        },
    )
