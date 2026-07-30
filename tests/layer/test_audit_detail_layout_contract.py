from pathlib import Path


def test_audit_detail_pages_do_not_render_redundant_counter_cards():
    templates = (
        Path("app/templates/admin/audit_event_detail.html"),
        Path("app/templates/admin/audit_appointment_protocol.html"),
    )

    for template_path in templates:
        source = template_path.read_text(encoding="utf-8")
        assert "audit-counters-grid" not in source
        assert "audit-counter-card" not in source
