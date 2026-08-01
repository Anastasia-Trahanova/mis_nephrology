from pathlib import Path

import pytest
from fastapi import HTTPException

from app.security.permissions import (
    CLINICAL_ROLES,
    ROLE_CHIEF_PHYSICIAN,
    ROLE_DEPARTMENT_HEAD,
    ROLE_DOCTOR,
    require_doctor_with_id,
)

ROOT = Path(__file__).resolve().parents[2]


class FakeRequest:
    def __init__(self, role: str, doctor_id=7):
        self.session = {"role": role, "doctor_id": doctor_id}


@pytest.mark.parametrize(
    "role",
    [ROLE_DOCTOR, ROLE_CHIEF_PHYSICIAN, ROLE_DEPARTMENT_HEAD],
)
def test_all_clinical_roles_can_work_as_doctor(role):
    assert role in CLINICAL_ROLES
    assert require_doctor_with_id(FakeRequest(role)) == 7


def test_admin_cannot_create_medical_appointment():
    with pytest.raises(HTTPException) as exc_info:
        require_doctor_with_id(FakeRequest("admin"))
    assert exc_info.value.status_code == 403


def test_schedule_accepts_all_clinical_roles():
    source = (ROOT / "app" / "routers" / "schedule.py").read_text(encoding="utf-8")
    assert "require_roles(request, ROLE_ADMIN, *CLINICAL_ROLES)" in source
    assert 'request.session.get("role") in CLINICAL_ROLES' in source


def test_patient_lists_accept_all_clinical_roles():
    source = (ROOT / "app" / "routers" / "patient_lists.py").read_text(encoding="utf-8")
    assert "require_roles(request, ROLE_ADMIN, *CLINICAL_ROLES)" in source


def test_patient_card_add_appointment_button_accepts_management_roles():
    source = (
        ROOT / "app" / "templates" / "patient_card" / "_appointments_sidebar.html"
    ).read_text(encoding="utf-8")
    assert source.count(
        "request.session.get('role') in ('doctor', 'chief_physician', 'department_head')"
    ) >= 2


def test_audit_is_still_admin_only():
    source = (ROOT / "app" / "routers" / "admin.py").read_text(encoding="utf-8")
    assert "require_admin(request)" in source
