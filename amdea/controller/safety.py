import os
from pathlib import Path
from amdea import config

DEMO_MODE: bool = os.getenv("AMDEA_SAFE_MODE", "false").lower() == "true"

def check_action_allowed(action_type: str) -> tuple[bool, str | None]:
    """Checks if an action type is allowed globally and in current mode."""
    if DEMO_MODE and action_type in config.BLOCKED_DEMO_ACTIONS:
        return False, f"Action '{action_type}' is blocked in safe demo mode."
    
    all_allowed = config.SAFE_ACTIONS | config.CONFIRMATION_REQUIRED_ACTIONS
    # Add system actions that might not be in the basic lists
    all_allowed.update({"respond_only", "clarify", "delete_custom_command", "run_command", "upload_file", "save_custom_command", "list_custom_commands"})
    
    if action_type not in all_allowed:
        return False, f"Action '{action_type}' is not in the allowed actions list."
    return True, None

def check_path_allowed(path_str: str) -> tuple[bool, str | None]:
    """Verifies that a file path is within allowed directories and safe."""
    try:
        path = Path(path_str).expanduser().resolve()
        
        # Check traversal
        if ".." in Path(path_str).parts:
            return False, "Path traversal ('..') detected."
            
        # Check against allowed roots
        is_safe = any(path.is_relative_to(root.resolve()) for root in config.ALLOWED_ROOTS)
        if not is_safe:
            return False, f"Path '{path_str}' is outside allowed directories."
            
        return True, None
    except Exception as e:
        return False, f"Invalid path: {str(e)}"

def check_url_safe(url: str) -> tuple[bool, str | None]:
    """Ensures a URL is safe (HTTPS only)."""
    if not url.startswith("https://"):
        return False, "Non-secure (HTTP) URLs are blocked. Only HTTPS is allowed."
    return True, None

def classify_risk_level(action_type: str, parameters: dict) -> str:
    """Classifies the risk level of an action."""
    if action_type == "run_command":
        return "critical"
    
    if action_type == "delete_file":
        if parameters.get("glob") or parameters.get("pattern"):
            return "critical"
        return "high"
        
    if action_type in ["send_email", "upload_file"]:
        return "high"
        
    if action_type in ["download_file", "move_file", "copy_file", "delete_custom_command"]:
        return "moderate"
        
    if action_type == "close_app" and parameters.get("force"):
        return "moderate"
        
    return "safe"

def validate_plan_safety(plan: dict) -> tuple[bool, list[str]]:
    """Validates the safety of an entire task plan."""
    errors = []
    for step in plan.get("steps", []):
        action = step["action_type"]
        params = step.get("parameters", {})
        
        # Check action
        allowed, reason = check_action_allowed(action)
        if not allowed:
            errors.append(f"Step {step['step_id']}: {reason}")
            
        # Check paths in parameters
        for key in ["path", "source", "destination"]:
            if key in params and isinstance(params[key], str):
                safe, reason = check_path_allowed(params[key])
                if not safe:
                    errors.append(f"Step {step['step_id']} ({action}): {reason}")
                    
        # Check URLs
        if "url" in params and isinstance(params["url"], str):
            safe, reason = check_url_safe(params["url"])
            if not safe:
                errors.append(f"Step {step['step_id']} ({action}): {reason}")
                
    return (len(errors) == 0), errors
