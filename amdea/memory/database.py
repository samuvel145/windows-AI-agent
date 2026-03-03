import sqlite3
import os
from amdea import config

def init_db() -> None:
    """Initializes the database and creates tables if they don't exist."""
    db_path = config.DB_PATH
    os.makedirs(db_path.parent, exist_ok=True)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Enable WAL mode
    cursor.execute("PRAGMA journal_mode=WAL;")
    
    # Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversation_turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user','assistant')),
        content TEXT NOT NULL,
        language TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS task_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id TEXT UNIQUE NOT NULL,
        session_id TEXT NOT NULL,
        intent TEXT,
        status TEXT NOT NULL CHECK(status IN ('completed','failed','cancelled','partial')),
        steps_total INTEGER,
        steps_done INTEGER,
        error_msg TEXT,
        duration_ms INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS action_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id TEXT,
        step_id INTEGER,
        action_type TEXT,
        parameters TEXT,
        outcome TEXT CHECK(outcome IN ('success','failure','skipped','cancelled')),
        error_code TEXT,
        duration_ms INTEGER,
        risk_level TEXT CHECK(risk_level IN ('safe','moderate','high','critical')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS custom_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trigger_phrase TEXT UNIQUE NOT NULL COLLATE NOCASE,
        plan_json TEXT NOT NULL,
        language TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_used_at DATETIME,
        use_count INTEGER DEFAULT 0
    );
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversation_session ON conversation_turns(session_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_session ON task_history(session_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_action_plan ON action_log(plan_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_custom_trigger ON custom_commands(trigger_phrase);")
    
    conn.commit()
    conn.close()

def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with row_factory, foreign keys, and 10s timeout."""
    conn = sqlite3.connect(config.DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
