"""Страница клинического справочника для всех авторизованных пользователей."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["clinical-reference"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/clinical-reference", response_class=HTMLResponse)
def clinical_reference_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="clinical_reference.html",
        context={
            "request": request,
            "page_title": "Клинический справочник",
        },
    )
