import os
import pystray
from PIL import Image, ImageDraw
import threading
import sys
from amdea import config

def create_state_icon(color):
    """Creates a 64x64 icon with a filled circle of the given color."""
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse([8, 8, 56, 56], fill=color, outline="white", width=2)
    return image

STATE_COLORS = {
    "IDLE": "grey",
    "LISTENING": "green",
    "PROCESSING": "yellow",
    "SPEAKING": "blue",
    "ERROR": "red"
}

class SystemTray:
    def __init__(self, agent):
        self.agent = agent
        self.icon = None
        self._state = "IDLE"
        self.icons = {state: create_state_icon(color) for state, color in STATE_COLORS.items()}

    def set_state(self, state: str) -> None:
        """Updates the tray icon image to match state. Wraps in try-except to avoid WinError crashes."""
        if state in self.icons and self.icon:
            try:
                self._state = state
                self.icon.icon = self.icons[state]
                self.icon.title = f"AMDEA — {state}"
            except Exception:
                # Silently catch pystray/Win32 cursor errors during shutdown/rapid updates
                pass

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(f"AMDEA v{config.VERSION}", lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Pause / Resume", self.toggle_agent),
            pystray.MenuItem("Settings", self.open_settings),
            pystray.MenuItem("Safe Mode: " + ("ON" if os.getenv("AMDEA_SAFE_MODE") == "true" else "OFF"), self.toggle_safe_mode),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.stop)
        )

    def toggle_agent(self, item):
        self.agent.is_running = not self.agent.is_running
        print(f"Agent running state: {self.agent.is_running}")

    def open_settings(self, item):
        from amdea.gui.settings import show_settings
        threading.Thread(target=show_settings, daemon=True).start()

    def toggle_safe_mode(self, item):
        current = os.getenv("AMDEA_SAFE_MODE", "false")
        os.environ["AMDEA_SAFE_MODE"] = "true" if current == "false" else "false"
        print(f"Safe mode: {os.environ['AMDEA_SAFE_MODE']}")

    def run(self) -> None:
        """Starts pystray in a daemon thread."""
        self.icon = pystray.Icon("AMDEA", self.icons["IDLE"], "AMDEA", self._build_menu())
        threading.Thread(target=self.icon.run, daemon=True).start()

    def stop(self, item=None) -> None:
        self.agent.stop()
        if self.icon:
            self.icon.stop()
        sys.exit(0)

