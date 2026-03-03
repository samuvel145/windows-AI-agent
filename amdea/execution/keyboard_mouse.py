import pyautogui
import keyboard
import platform
import io
import pathlib
import time
import pyperclip

# Security: Failsafe if user slams mouse into corner
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

SAFE_KEY_COMBOS: frozenset = frozenset({
    "ctrl+c", "ctrl+v", "ctrl+z", "ctrl+a", "ctrl+s", 
    "alt+tab", "ctrl+tab", "enter", "escape", "tab", "backspace"
})

def type_text(text: str, interval: float = 0.03) -> None:
    """
    Simulates typing text via keyboard.
    For non-ASCII characters: use pyperclip + paste fallback.
    """
    if all(ord(c) < 128 for c in text):
        pyautogui.write(text, interval=interval)
    else:
        # Fallback for unicode
        pyperclip.copy(text)
        if platform.system() == "Darwin":
            keyboard.send("cmd+v")
        else:
            keyboard.send("ctrl+v")

def key_press(keys: list[str], modifiers: list[str] = []) -> None:
    """Presses a key combination (e.g. ['c'], ['ctrl'])."""
    combo = "+".join(modifiers + keys)
    keyboard.send(combo)

def key_press_safe(keys: list[str], modifiers: list[str] = []) -> None:
    """Checks combo against SAFE_KEY_COMBOS before pressing."""
    combo = "+".join(modifiers + keys).lower()
    if combo not in SAFE_KEY_COMBOS:
        raise ValueError(f"Key combination '{combo}' is not in the safe whitelist.")
    key_press(keys, modifiers)

def mouse_click(x: int, y: int, button: str = "left") -> None:
    """Clicks the mouse at specified coordinates."""
    pyautogui.click(x, y, button=button)

def take_screenshot(save_path: str | None = None) -> bytes:
    """
    Takes a screenshot. If save_path given, saves PNG. Returns PNG bytes.
    (Vision analysis is planned for v2).
    """
    screenshot = pyautogui.screenshot()
    img_byte_arr = io.BytesIO()
    screenshot.save(img_byte_arr, format='PNG')
    if save_path:
        path = pathlib.Path(save_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        screenshot.save(str(path))
    return img_byte_arr.getvalue()

def wait(seconds: float) -> None:
    """Pauses execution for a specified duration."""
    time.sleep(seconds)
