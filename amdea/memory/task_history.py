import json
from amdea.memory.database import get_connection

def create_task(plan_id: str, session_id: str, intent: str, steps_total: int) -> None:
    """Initializes a task history entry."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO task_history (plan_id, session_id, intent, steps_total, status) VALUES (?, ?, ?, ?, 'partial')",
        (plan_id, session_id, intent, steps_total)
    )
    conn.commit()
    conn.close()

def complete_task(plan_id: str, steps_done: int, duration_ms: int) -> None:
    """Marks a task as successfully completed."""
    conn = get_connection()
    conn.execute(
        "UPDATE task_history SET status = 'completed', steps_done = ?, duration_ms = ? WHERE plan_id = ?",
        (steps_done, duration_ms, plan_id)
    )
    conn.commit()
    conn.close()

def fail_task(plan_id: str, steps_done: int, error_msg: str, duration_ms: int) -> None:
    """Marks a task as failed."""
    conn = get_connection()
    conn.execute(
        "UPDATE task_history SET status = 'failed', steps_done = ?, error_msg = ?, duration_ms = ? WHERE plan_id = ?",
        (steps_done, error_msg, duration_ms, plan_id)
    )
    conn.commit()
    conn.close()

def cancel_task(plan_id: str, steps_done: int) -> None:
    """Marks a task as cancelled by the user."""
    conn = get_connection()
    conn.execute(
        "UPDATE task_history SET status = 'cancelled', steps_done = ? WHERE plan_id = ?",
        (steps_done, plan_id)
    )
    conn.commit()
    conn.close()

def log_action(plan_id: str, step_id: int, action_type: str, parameters: dict, 
               outcome: str, error_code: str = None, duration_ms: int = None, risk_level: str = 'safe') -> None:
    """Logs an individual action within a task plan."""
    params_json = json.dumps(parameters)
    conn = get_connection()
    conn.execute(
        "INSERT INTO action_log (plan_id, step_id, action_type, parameters, outcome, error_code, duration_ms, risk_level) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (plan_id, step_id, action_type, params_json, outcome, error_code, duration_ms, risk_level)
    )
    conn.commit()
    conn.close()

def get_recent_tasks(limit: int = 20) -> list[dict]:
    """Retrieves recent tasks from the history."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM task_history ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_task_actions(plan_id: str) -> list[dict]:
    """Retrieves all logged actions for a specific plan ID."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM action_log WHERE plan_id = ? ORDER BY step_id ASC", (plan_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
