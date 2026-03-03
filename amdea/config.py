from pathlib import Path

PROJECT_NAME = "AMDEA"
VERSION = "0.1.0"
DB_PATH = Path.home() / ".amdea" / "amdea.db"
LOG_DIR = Path.home() / ".amdea" / "logs"

ALLOWED_ROOTS = [
    Path("C:/"), # Allow full C drive access
    Path("D:/") if Path("D:/").exists() else Path.home(), # Allow D if exists, else home
    Path.home(),
]

SAFE_ACTIONS = {
    "open_app", "close_app", "switch_app", "open_browser", "navigate_url",
    "browser_search", "click_element", "read_element", "fill_form",
    "create_file", "read_file", "edit_file", "create_folder", "list_folder",
    "search_files", "rename_file", "open_file",
    "type_text", "key_press", "mouse_click", "mouse_move", "scroll",
    "wait", "respond_only", "clarify", "navigate_explorer",
    "save_custom_command", "list_custom_commands", "run_command",
    "media_play_pause", "media_next", "media_prev", "media_mute",
    "minimize_window", "maximize_window", "show_desktop", "screenshot",
    "set_volume", "check_internet", "toggle_wifi", "toggle_bluetooth",
    "system_lock", "system_sleep",
    "get_element_attribute", "find_file"
}

CONFIRMATION_REQUIRED_ACTIONS = {
    "delete_file", "move_file", "copy_file",
    "send_email", "download_file", "upload_file", 
    "delete_custom_command"
}

BLOCKED_DEMO_ACTIONS = {
    "run_command", "delete_file", "upload_file"
}

MAX_CONVERSATION_TURNS = 10
STT_TIMEOUT_SECONDS = 15 # Increased for complex commands
CONFIRMATION_TIMEOUT_SECONDS = 15
MAX_STEPS_PER_PLAN = 20
MAX_RETRIES_PER_STEP = 2
SILENCE_TIMEOUT_MS = 600 # Faster response after speech ends
