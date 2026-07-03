"""
ЛЕГЕНДА
Файл: app/routers/ckd_registry.py
Назначение: административная страница регистра ХБП.
Доступ: только пользователь с ролью admin.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..registry_queries import get_ckd_registry_dashboard

router = APIRouter(tags=["ckd_registry"])
templates = Jinja2Templates(directory="app/templates")


def require_admin(request: Request) -> None:
    """Пускает в регистр только администратора."""
    if request.session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Раздел доступен только администратору")


@router.get("/ckd-registry", response_class=HTMLResponse)
def ckd_registry_dashboard(request: Request):
    require_admin(request)
    dashboard = get_ckd_registry_dashboard()
    return templates.TemplateResponse(
        "ckd_registry.html",
        {
            "request": request,
            "dashboard": dashboard,
            "summary": dashboard.get("summary", {}),
            "queues": dashboard.get("queues", {}),
            "doctor_high_risk": dashboard.get("doctor_high_risk", []),
            "location_incomplete": dashboard.get("location_incomplete", []),
        },
    )
