from pathlib import Path


def test_walk_in_router_passes_device_active_location():
    root = Path(__file__).resolve().parents[2]
    source = (root / "app/routers/schedule.py").read_text(encoding="utf-8")
    assert "get_session_active_location" in source
    assert "active_location_id = get_session_active_location" in source
    assert "preferred_location_id=active_location_id" in source


def test_walk_in_repository_accepts_preferred_location():
    root = Path(__file__).resolve().parents[2]
    source = (root / "app/repositories/schedule.py").read_text(encoding="utf-8")
    assert "preferred_location_id: int | None = None" in source
    assert "_doctor_location_allowed(cur, doctor_id, int(preferred_location_id))" in source
    assert "UPDATE schedule_entries SET location_id = %s" in source
