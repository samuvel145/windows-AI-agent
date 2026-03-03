from amdea.memory.database import get_connection
from datetime import datetime

def save_command(trigger_phrase: str, plan_json: str, language: str = None) -> None:
    """Saves or updates a custom voice command (shortcut)."""
    normalized_phrase = trigger_phrase.lower().strip()
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO custom_commands (trigger_phrase, plan_json, language) VALUES (?, ?, ?)",
        (normalized_phrase, plan_json, language)
    )
    conn.commit()
    conn.close()

def get_command(trigger_phrase: str) -> dict | None:
    """Retrieves a command by its trigger phrase and updates usage metrics."""
    normalized_phrase = trigger_phrase.lower().strip()
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM custom_commands WHERE trigger_phrase = ?", (normalized_phrase,))
    row = cursor.fetchone()
    
    if row:
        command = dict(row)
        conn.execute(
            "UPDATE custom_commands SET last_used_at = CURRENT_TIMESTAMP, use_count = use_count + 1 WHERE id = ?",
            (command["id"],)
        )
        conn.commit()
        conn.close()
        return command
    
    conn.close()
    return None

def list_commands() -> list[dict]:
    """Lists all custom commands ordered by usage count."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM custom_commands ORDER BY use_count DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_command(trigger_phrase: str) -> bool:
    """Deletes a custom command. Returns True if successful."""
    normalized_phrase = trigger_phrase.lower().strip()
    conn = get_connection()
    cursor = conn.execute("DELETE FROM custom_commands WHERE trigger_phrase = ?", (normalized_phrase,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def search_commands(partial: str) -> list[dict]:
    """Searches for commands matching a partial trigger phrase."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM custom_commands WHERE trigger_phrase LIKE ?", (f"%{partial}%",))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
