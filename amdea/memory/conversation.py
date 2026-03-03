from amdea.memory.database import get_connection
from datetime import datetime, timedelta

def add_turn(session_id: str, role: str, content: str, language: str = None) -> None:
    """Adds a conversation turn to the database."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO conversation_turns (session_id, role, content, language) VALUES (?, ?, ?, ?)",
        (session_id, role, content, language)
    )
    conn.commit()
    conn.close()

def get_recent_turns(session_id: str, limit: int = 10) -> list[dict]:
    """Retrieves the most recent conversation turns for a session."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT role, content FROM conversation_turns WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
        (session_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    
    # Return in oldest-first order for LLM context
    turns = [{"role": row["role"], "content": row["content"]} for row in rows]
    return list(reversed(turns))

def purge_old_sessions(days: int = 30) -> int:
    """Deletes conversation turns older than the specified number of days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = get_connection()
    cursor = conn.execute("DELETE FROM conversation_turns WHERE timestamp < ?", (cutoff,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

def count_turns(session_id: str) -> int:
    """Returns the total number of turns in a session."""
    conn = get_connection()
    cursor = conn.execute("SELECT COUNT(*) FROM conversation_turns WHERE session_id = ?", (session_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def trim_session(session_id: str, keep_last: int = 100) -> None:
    """Keeps only the most recent turns in a session, deleting the rest."""
    conn = get_connection()
    # Find the ID of the Nth most recent turn
    cursor = conn.execute(
        "SELECT id FROM conversation_turns WHERE session_id = ? ORDER BY timestamp DESC LIMIT 1 OFFSET ?",
        (session_id, keep_last - 1)
    )
    row = cursor.fetchone()
    if row:
        conn.execute("DELETE FROM conversation_turns WHERE session_id = ? AND id < ?", (session_id, row["id"]))
        conn.commit()
    conn.close()
