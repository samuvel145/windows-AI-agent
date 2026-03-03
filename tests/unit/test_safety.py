import pytest
import os
from amdea.controller import safety

def test_safe_action_allowed():
    allowed, reason = safety.check_action_allowed("open_app")
    assert allowed is True
    assert reason is None

def test_unknown_action_blocked():
    allowed, reason = safety.check_action_allowed("hack_the_planet")
    assert allowed is False
    assert "not in the allowed actions" in reason

def test_demo_mode_blocks_run_command(monkeypatch):
    import amdea.controller.safety as s
    monkeypatch.setattr(s, "DEMO_MODE", True)
    allowed, reason = s.check_action_allowed("run_command")
    assert allowed is False
    assert "blocked in safe demo mode" in reason

def test_path_traversal_blocked():
    allowed, reason = safety.check_path_allowed("~/Downloads/../../etc/passwd")
    assert allowed is False
    # Pathlib resolve might handle the .. if the path exists, but our ".." check catches it
    assert "traversal" in reason or "outside" in reason

def test_http_url_blocked():
    allowed, reason = safety.check_url_safe("http://example.com")
    assert allowed is False
    assert "HTTPS" in reason

def test_risk_critical_run_command():
    risk = safety.classify_risk_level("run_command", {})
    assert risk == "critical"

def test_full_plan_safety_pass():
    plan = {
        "steps": [
            {"step_id": 1, "action_type": "open_app", "parameters": {"app_name": "chrome"}}
        ]
    }
    ok, errors = safety.validate_plan_safety(plan)
    assert ok is True
    assert len(errors) == 0
