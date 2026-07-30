from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_schedule_loads_patient_flow_after_main_script():
    source = (ROOT / "app" / "templates" / "schedule" / "index.html").read_text(
        encoding="utf-8"
    )
    main_script = "js/schedule/schedule-page.js"
    patient_flow = "js/schedule/schedule-patient-flow.js"

    assert main_script in source
    assert patient_flow in source
    assert source.index(main_script) < source.index(patient_flow)


def test_patient_flow_has_required_choices_and_uses_clicked_entry():
    source = (
        ROOT / "app" / "static" / "js" / "schedule" / "schedule-patient-flow.js"
    ).read_text(encoding="utf-8")

    assert "Посмотреть ЭМК пациента" in source
    assert "Перейти к заполнению данных приёма" in source
    assert "Перезаписать пациента на сегодня" in source
    assert "оставить будущую запись" in source
    assert 'createWalkIn("cancel_and_create")' in source
    assert 'createWalkIn("keep_and_create")' in source
    assert "scheduled_entry_id: currentEntry.id" in source
    assert "scheduledStart > new Date()" in source


def test_schedule_entry_details_and_future_rebooking_contract():
    router_source = (ROOT / "app" / "routers" / "schedule.py").read_text(encoding="utf-8")
    repository_source = (ROOT / "app" / "repositories" / "schedule.py").read_text(encoding="utf-8")

    assert '@router.get("/schedule/api/entries/{entry_id}")' in router_source
    assert '"patient_id": item["patient_id"]' in router_source
    assert '"date_iso": item["date_iso"]' in router_source
    assert '"appointment_id": item.get("appointment_id")' in router_source
    assert 'scheduled["ends_at"] <= current' in repository_source
    assert 'scheduled["starts_at"] > current + timedelta(days=30)' not in repository_source
