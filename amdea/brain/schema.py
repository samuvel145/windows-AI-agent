import json
import jsonschema
from amdea import config

TASK_PLAN_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["plan_id", "detected_language", "steps", "tts_response"],
    "properties": {
        "plan_id": {"type": "string"},
        "detected_language": {"type": "string", "minLength": 2},
        "intent_summary": {"type": "string"},
        "steps": {
            "type": "array",
            "minItems": 1,
            "maxItems": config.MAX_STEPS_PER_PLAN,
            "items": {
                "type": "object",
                "required": ["step_id", "action_type", "parameters", "requires_confirmation"],
                "properties": {
                    "step_id": {"type": "integer", "minimum": 1},
                    "action_type": {
                        "type": "string",
                        "enum": list(config.SAFE_ACTIONS | config.CONFIRMATION_REQUIRED_ACTIONS)
                    },
                    "parameters": {"type": "object"},
                    "requires_confirmation": {"type": "boolean"},
                    "confirmed": {"type": "boolean", "default": False},
                    "depends_on": {"type": "array", "items": {"type": "integer"}, "default": []},
                    "on_failure": {"type": "string", "enum": ["abort", "skip", "retry"], "default": "abort"}
                }
            }
        },
        "tts_response": {"type": "string"},
        "clarification_needed": {"type": "boolean", "default": False},
        "clarification_question": {"type": "string"}
    }
}

def validate_plan(plan_dict: dict) -> tuple[bool, str | None]:
    """Validates a plan against the JSON schema."""
    try:
        jsonschema.validate(instance=plan_dict, schema=TASK_PLAN_SCHEMA)
        return True, None
    except jsonschema.ValidationError as e:
        return False, f"Validation Error: {e.message}"
    except jsonschema.SchemaError as e:
        return False, f"Schema Error: {e.message}"

def parse_and_validate(raw_json: str) -> tuple[dict | None, str | None]:
    """Parses raw JSON string and validates it."""
    try:
        # Strip markdown fences if present
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
            
        plan = json.loads(cleaned)
        is_valid, error = validate_plan(plan)
        if is_valid:
            return plan, None
        return None, error
    except json.JSONDecodeError as e:
        return None, f"JSON Decode Error: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"
