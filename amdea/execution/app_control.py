import os
import subprocess
import shutil
import psutil
import platform
from pathlib import Path

APP_NAME_MAP = {
    "chrome": {
        "windows": "chrome.exe",
        "darwin": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "linux": "google-chrome"
    },
    "firefox": {
        "windows": "firefox.exe",
        "darwin": "/Applications/Firefox.app/Contents/MacOS/firefox",
        "linux": "firefox"
    },
    "notepad": {
        "windows": "notepad.exe",
        "darwin": "TextEdit",
        "linux": "gedit"
    },
    "vscode": {
        "windows": "code.cmd",
        "darwin": "code",
        "linux": "code"
    },
    "spotify": {
        "windows": "spotify.exe",
        "darwin": "Spotify",
        "linux": "spotify"
    },
    "fileexplorer": {
        "windows": "explorer.exe",
        "darwin": "Finder",
        "linux": "nautilus"
    },
    "wordpad": {
        "windows": r"C:\Program Files\Windows NT\Accessories\wordpad.exe"
    },
    "calculator": {
        "windows": "calc.exe",
        "darwin": "Calculator",
        "linux": "gnome-calculator"
    },
    "taskmanager": {
        "windows": "taskmgr.exe",
        "darwin": "Activity Monitor",
        "linux": "top"
    },
    "word": {
        "windows": "winword.exe" # Microsoft Word
    },
    "excel": {
        "windows": "excel.exe"
    },
    "powerpoint": {
        "windows": "powerpnt.exe"
    }
}

class AppNotFoundError(Exception): pass

def _find_app_path_powershell(app_name: str) -> str | None:
    """Uses PowerShell to find an application's executable path or AppID."""
    if platform.system().lower() != "windows":
        return None
        
    try:
        # Search for the app name or its "short" version
        search_terms = [app_name]
        if " " in app_name:
            search_terms.append(app_name.split()[-1]) # Try just the last word (e.g. 'Word' from 'Microsoft Word')

        for term in search_terms:
            cmd = f"Get-StartApps | Where-Object {{ $_.Name -like '*{term}*' }} | Select-Object -ExpandProperty AppID -First 1"
            result = subprocess.check_output(["powershell", "-NoProfile", "-Command", cmd], text=True).strip()
            if result:
                return result
    except:
        return None
    return None

def open_app(app_name: str, args: list[str] = []) -> bool:
    """Launches an application by name or common alias."""
    os_name = platform.system().lower()
    norm_name = app_name.lower().replace(" ", "").replace("-", "")
    
    # Common user-phrased aliases
    alias_map = {
        "filemanagement": "fileexplorer",
        "wordpack": "wordpad",
        "wordpad": "wordpad",
        "word": "word",
        "msword": "word",
        "microsoftword": "word",
        "explorer": "fileexplorer",
        "calc": "calculator",
        "vsc": "vscode",
        "code": "vscode"
    }
    norm_name = alias_map.get(norm_name, norm_name)
    
    executable = None
    if norm_name in APP_NAME_MAP:
        executable = APP_NAME_MAP[norm_name].get(os_name) or APP_NAME_MAP[norm_name].get("linux")
        if executable:
            full_path = shutil.which(executable)
            if full_path: 
                executable = full_path
            elif os_name == "windows" and not os.path.isabs(executable):
                # Fallback for Wordpad/Notepad which might not be in PATH
                common_paths = [
                    r"C:\Program Files\Windows NT\Accessories\wordpad.exe",
                    r"C:\Windows\System32\notepad.exe",
                    r"C:\Windows\explorer.exe",
                    r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
                    r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE",
                    r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
                    r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE"
                ]
                for cp in common_paths:
                    if executable.lower() in cp.lower() and os.path.exists(cp):
                        executable = cp
                        break

    if not executable:
        executable = shutil.which(app_name) or shutil.which(norm_name)
        
    if executable:
        try:
            subprocess.Popen([executable] + args, start_new_session=True)
            return True
        except FileNotFoundError:
            pass # Fall through to PowerShell
            
    # Fallback to PowerShell search for Windows apps (UWP, Start menu apps)
    app_id = _find_app_path_powershell(app_name)
    if not app_id and norm_name != app_name:
        app_id = _find_app_path_powershell(norm_name)
        
    if app_id:
        subprocess.Popen(["powershell", "-NoProfile", "-Command", f"Explorer.exe shell:AppsFolder\\{app_id}"], start_new_session=True)
        return True
        
    # Final check: if 'word' or 'wordpad' failed, try notepad as last resort
    if norm_name in ["word", "wordpad"]:
        try:
            return open_app("notepad", args)
        except: pass

    raise AppNotFoundError(f"Could not find application: {app_name}. If it's a browser site, ask me to 'open chrome' first.")

def close_app(app_name: str, force: bool = False) -> bool:
    """Closes an application by process name."""
    found = False
    for proc in psutil.process_iter(['name', 'pid']):
        try:
            if app_name.lower() in proc.info['name'].lower():
                if force:
                    proc.kill()
                else:
                    proc.terminate()
                found = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found

def is_app_running(app_name: str) -> bool:
    """Checks if an application is currently running."""
    for proc in psutil.process_iter(['name']):
        try:
            if app_name.lower() in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def list_running_apps() -> list[str]:
    """Returns a list of unique running process names."""
    apps = set()
    for proc in psutil.process_iter(['name']):
        try:
            apps.add(proc.info['name'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(list(apps))

def open_file(file_path: str) -> bool:
    """Opens a file with its default application. Falls back to search if not found."""
    path = Path(file_path).expanduser().resolve()
    
    if not path.exists():
        # Smart Fallback: If path doesn't exist, try to find it in common directories
        from amdea.execution.filesystem import fuzzy_find_file
        filename = path.name
        search_dirs = [
            path.parent,
            Path.home() / "Videos",
            Path.home() / "Downloads",
            Path.home() / "Desktop",
            Path.home() / "Documents"
        ]
        
        for sd in search_dirs:
            if sd.exists():
                found = fuzzy_find_file(str(sd), filename)
                if found:
                    path = Path(found)
                    break
        
        if not path.exists():
            raise FileNotFoundError(f"Could not find file: {file_path}")
            
    # On Windows use 'start' to open with default app
    subprocess.Popen(['cmd', '/c', 'start', '', str(path)], start_new_session=True)
    return True
