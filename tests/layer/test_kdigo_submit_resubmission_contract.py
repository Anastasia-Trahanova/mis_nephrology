from pathlib import Path


def test_kdigo_resubmit_is_deferred_outside_original_submit_event():
    js = Path("app/static/js/kdigo_risk_preview.js").read_text(encoding="utf-8")
    assert "window.setTimeout(function ()" in js
    assert "const submitter = event.submitter || null;" in js
    assert "form.requestSubmit(submitter)" in js
    assert "HTMLFormElement.prototype.submit.call(form)" in js


def test_kdigo_script_cache_version_bumped():
    template = Path("app/templates/appointment_form/_kdigo_risk_preview.html").read_text(encoding="utf-8")
    assert "kdigo-server-v5" in template
