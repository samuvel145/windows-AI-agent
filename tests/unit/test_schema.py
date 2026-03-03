import pytest
import json
from amdea.brain.schema import parse_and_validate

def test_valid_minimal_plan():
    raw = {
        "plan_id": "test-123",
        "detected_language": "en",
        "intent_summary": "Open notepad",
        "steps": [{
            "step_id": 1,
            "action_type": "open_app",
            "parameters": {"app_name": "notepad"},
            "requires_confirmation": False
        }],
        "tts_response": "Opening notepad."
    }
    plan, error = parse_and_validate(json.dumps(raw))
    assert plan is not None
    assert error is None
    assert plan["plan_id"] == "test-123"

def test_missing_required_field():
    raw = {"plan_id": "test"}
    plan, error = parse_and_validate(json.dumps(raw))
    assert plan is None
    assert "detected_language" in error

def test_invalid_action_type():
    raw = {
        "plan_id": "test",
        "detected_language": "en",
        "steps": [{
            "step_id": 1,
            "action_type": "format_hard_drive",
            "parameters": {},
            "requires_confirmation": False
        }],
        "tts_response": "ok"
    }
    plan, error = parse_and_validate(json.dumps(raw))
    if error: print(f"DEBUG ERROR: {error}")
    assert plan is None
    # jsonschema 4.x+ might not include the word 'action_type' in the message itself
    assert "not one of" in error or "action_type" in error

def test_markdown_fences_stripped():
    raw_dict = {
        "plan_id": "test",
        "detected_language": "en",
        "steps": [{"step_id": 1, "action_type": "respond_only", "parameters": {}, "requires_confirmation": False}],
        "tts_response": "ok"
    }
    raw_str = f"```json\n{json.dumps(raw_dict)}\n```"
    plan, error = parse_and_validate(raw_str)
    assert plan is not None
    assert plan["plan_id"] == "test"

def test_clarification_plan():
    raw = {
        "plan_id": "test",
        "detected_language": "en",
        "steps": [{"step_id": 1, "action_type": "respond_only", "parameters": {}, "requires_confirmation": False}],
        "tts_response": "Need help",
        "clarification_needed": True,
        "clarification_question": "Which file?"
    }
    plan, error = parse_and_validate(json.dumps(raw))
    if error: print(error)
    assert plan is not None
    assert plan.get("clarification_needed") is True
