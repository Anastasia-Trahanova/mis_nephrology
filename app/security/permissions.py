"""
Назначение файла: базовые ролевые проверки МИС.

Как работает:
- читает текущего пользователя из request.session;
- отличает администратора от врача;
- даёт единое место для проверки admin-only и doctor-only страниц;
- возвращает 403, если пользователь вошёл, но его роль не подходит.
"""

from __future__ import annotations

from fastapi import HTTPException, Request


ROLE_ADMIN = "admin"
ROLE_DOCTOR = "doctor"
ROLE_CHIEF_PHYSICIAN = "chief_physician"
ROLE_DEPARTMENT_HEAD = "department_head"

CLINICAL_ROLES = frozenset(
    {
        ROLE_DOCTOR,
        ROLE_CHIEF_PHYSICIAN,
        ROLE_DEPARTMENT_HEAD,
    }
)
ALLOWED_ROLES = {ROLE_ADMIN, *CLINICAL_ROLES}


def current_user(request: Request) -> dict:
    """Возвращает минимальные данные текущего пользователя из session."""
    return {
        "user_id": request.session.get("user_id"),
        "login": request.session.get("login"),
        "display_name": request.session.get("display_name"),
        "role": request.session.get("role"),
        "doctor_id": request.session.get("doctor_id"),
        "patient_id": request.session.get("patient_id"),
    }


def current_role(request: Request) -> str | None:
    """Возвращает роль текущего пользователя."""
    role = request.session.get("role")
    return str(role).strip().lower() if role else None


def is_admin(request: Request) -> bool:
    """True, если текущий пользователь — администратор."""
    return current_role(request) == ROLE_ADMIN


def is_doctor(request: Request) -> bool:
    """True для обычного врача, главного врача и заведующего отделением."""
    return current_role(request) in CLINICAL_ROLES


def require_roles(request: Request, *allowed_roles: str) -> None:
    """Проверяет, что пользователь вошёл с одной из разрешённых ролей."""
    normalized = {role.strip().lower() for role in allowed_roles if role}
    if current_role(request) not in normalized:
        raise HTTPException(status_code=403, detail="Недостаточно прав для открытия раздела")


def require_admin(request: Request) -> None:
    """Пускает только администратора."""
    require_roles(request, ROLE_ADMIN)


def require_doctor_with_id(request: Request) -> int:
    """
    Пускает медицинского сотрудника, привязанного к записи doctors.

    Обычный врач, главный врач и заведующий отделением имеют одинаковые
    клинические права. Администратор не может создавать медицинские приёмы,
    а doctor_id берётся только из сессии, не из HTML-формы.
    """
    require_roles(request, *CLINICAL_ROLES)

    doctor_id = request.session.get("doctor_id")
    try:
        doctor_id_int = int(doctor_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=403,
            detail="Пользователь-врач не привязан к записи врача",
        )

    if doctor_id_int <= 0:
        raise HTTPException(
            status_code=403,
            detail="Пользователь-врач не привязан к записи врача",
        )

    return doctor_id_int
