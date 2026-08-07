from pathlib import Path

from app.services import active_location_service as service
from app.services.word_export.header import _location_name


class _Request:
    def __init__(self, cookies=None):
        self.cookies = cookies or {}
        self.session = {}


class _Response:
    def __init__(self):
        self.cookie = None

    def set_cookie(self, **kwargs):
        self.cookie = kwargs


def test_two_locations_require_choice_without_device_cookie():
    request = _Request()
    locations = [{"id": 1}, {"id": 7}]
    assert service.choose_active_location_on_login(request, 3, locations) is None


def test_device_cookie_is_scoped_to_doctor_and_allowed_location():
    locations = [{"id": 1}, {"id": 7}]
    assert service.choose_active_location_on_login(
        _Request({service.ACTIVE_LOCATION_COOKIE_NAME: "3:7"}), 3, locations
    ) == 7
    assert service.choose_active_location_on_login(
        _Request({service.ACTIVE_LOCATION_COOKIE_NAME: "4:7"}), 3, locations
    ) is None
    assert service.choose_active_location_on_login(
        _Request({service.ACTIVE_LOCATION_COOKIE_NAME: "3:999"}), 3, locations
    ) is None


def test_single_location_is_selected_automatically():
    assert service.choose_active_location_on_login(_Request(), 3, [{"id": 1}]) == 1


def test_successful_preference_is_kept_in_session_and_cookie():
    request = _Request()
    response = _Response()
    service.set_active_location_preference(request, response, 3, 7)
    assert request.session[service.ACTIVE_LOCATION_SESSION_KEY] == 7
    assert response.cookie["value"] == "3:7"


def test_fesfarm_word_header_name_is_unchanged():
    info = {
        "location_name": "Отделение гемодиализа",
        "branch_name": "ФЕСФАРМ НН",
        "company_name": "ООО «КОМПАНИЯ «ФЕСФАРМ»",
    }
    assert _location_name(info) == (
        "Отделение гемодиализа, Филиал «ФЕСФАРМ НН», "
        "ООО «КОМПАНИЯ «ФЕСФАРМ»"
    )


def test_gb33_does_not_get_false_filial_prefix():
    info = {
        "location_name": "ГОРОДСКОЙ НЕФРОЛОГИЧЕСКИЙ ЦЕНТР",
        "branch_name": "ГОРОДСКАЯ БОЛЬНИЦА № 33",
        "company_name": "ГОРОДСКАЯ БОЛЬНИЦА № 33",
    }
    assert _location_name(info) == (
        "ГОРОДСКОЙ НЕФРОЛОГИЧЕСКИЙ ЦЕНТР, ГОРОДСКАЯ БОЛЬНИЦА № 33"
    )


def test_appointment_templates_use_active_location_fallback():
    root = Path(__file__).resolve().parents[2]
    repeat = (root / "app/templates/new_appointment.html").read_text(encoding="utf-8")
    primary = (root / "app/templates/new_patient.html").read_text(encoding="utf-8")
    assert "not schedule_entry and active_location_id" in repeat
    assert "not scheduled_primary and active_location_id" in primary
