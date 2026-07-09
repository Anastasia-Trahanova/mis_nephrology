"""
Назначение файла: базовые ролевые проверки МИС.

Как работает:
- читает текущего пользователя из request.session;
- отличает администратора от врача;
- даёт единое место для проверки admin-only страниц;
- возвращает 403, если пользователь вошёл, но его роль не подходит.

Что редактировать здесь:
- список допустимых ролей;
- helper-функции require_admin / require_roles;
- будущую роль заведующего или главного врача, когда она появится.

Что не редактировать здесь:
- idle-timeout и login/logout — они в app/routers/auth.py;
- таблицу аудита — она в app/repositories/audit_log.py;
- медицинские SQL-запросы и шаблоны карточки пациента.
"""

from __future__ import annotations

from fastapi import HTTPException, Request


ROLE_ADMIN = "admin"
ROLE_DOCTOR = "doctor"
ALLOWED_ROLES = {ROLE_ADMIN, ROLE_DOCTOR}


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
    """True, если текущий пользователь — врач."""
    return current_role(request) == ROLE_DOCTOR


def require_roles(request: Request, *allowed_roles: str) -> None:
    """Проверяет, что пользователь вошёл с одной из разрешённых ролей."""
    normalized = {role.strip().lower() for role in allowed_roles if role}
    if current_role(request) not in normalized:
        raise HTTPException(status_code=403, detail="Недостаточно прав для открытия раздела")


def require_admin(request: Request) -> None:
    """Пускает только администратора."""
    require_roles(request, ROLE_ADMIN)
