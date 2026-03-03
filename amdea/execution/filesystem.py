import pathlib
import shutil
import glob
from amdea.controller.safety import check_path_allowed

def create_file(path_str: str, content: str = "") -> str:
    """Creates a file with the given content."""
    check, reason = check_path_allowed(path_str)
    if not check:
        raise PermissionError(reason)
        
    path = pathlib.Path(path_str).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)

def read_file(path_str: str) -> str:
    """Reads and returns the content of a file."""
    check, reason = check_path_allowed(path_str)
    if not check:
        raise PermissionError(reason)
        
    path = pathlib.Path(path_str).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path_str}")
    return path.read_text(encoding="utf-8")

def move_file(source: str, destination: str) -> str:
    """Moves a file or directory."""
    for p in [source, destination]:
        check, reason = check_path_allowed(p)
        if not check:
            raise PermissionError(reason)
            
    src = pathlib.Path(source).expanduser().resolve()
    dst = pathlib.Path(destination).expanduser().resolve()
    
    if dst.is_dir():
        dst = dst / src.name
        
    shutil.move(str(src), str(dst))
    return str(dst)

def copy_file(source: str, destination: str) -> str:
    """Copies a file."""
    for p in [source, destination]:
        check, reason = check_path_allowed(p)
        if not check:
            raise PermissionError(reason)
            
    src = pathlib.Path(source).expanduser().resolve()
    dst = pathlib.Path(destination).expanduser().resolve()
    
    if dst.is_dir():
        dst = dst / src.name
        
    shutil.copy2(str(src), str(dst))
    return str(dst)

def delete_file(path_str: str) -> bool:
    """Deletes a file or directory recursively."""
    check, reason = check_path_allowed(path_str)
    if not check:
        raise PermissionError(reason)
        
    path = pathlib.Path(path_str).expanduser().resolve()
    if path.is_file() or path.is_symlink():
        path.unlink()
        return True
    elif path.is_dir():
        shutil.rmtree(path)
        return True
    return False

def delete_files_glob(path_str: str, pattern: str) -> list[str]:
    """Deletes files matching a glob pattern. Returns list of deleted paths."""
    check, reason = check_path_allowed(path_str)
    if not check:
        raise PermissionError(reason)
        
    base_path = pathlib.Path(path_str).expanduser().resolve()
    deleted = []
    for p in base_path.glob(pattern):
        # Additional safety check for each matched file
        if check_path_allowed(str(p))[0]:
            if p.is_file():
                p.unlink()
                deleted.append(str(p))
            elif p.is_dir():
                shutil.rmtree(p)
                deleted.append(str(p))
    return deleted

def list_folder(path_str: str, filter_ext: str | None = None) -> list[dict]:
    """
    Lists contents of a folder with rich metadata.
    Returns list of {"name": str, "path": str, "is_dir": bool, "size_bytes": int}
    """
    check, reason = check_path_allowed(path_str)
    if not check:
        raise PermissionError(reason)
        
    path = pathlib.Path(path_str).expanduser().resolve()
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path_str}")
        
    items = []
    for f in path.iterdir():
        if filter_ext and not f.name.endswith(filter_ext):
            continue
            
        try:
            items.append({
                "name": f.name,
                "path": str(f.resolve()),
                "is_dir": f.is_dir(),
                "size_bytes": f.stat().st_size if f.is_file() else 0
            })
        except OSError:
            continue
    return items

def count_glob(path_str: str, pattern: str) -> int:
    """Returns count of matching files without deleting. For confirmation prompts."""
    check, reason = check_path_allowed(path_str)
    if not check:
        raise PermissionError(reason)
        
    path = pathlib.Path(path_str).expanduser().resolve()
    return len(list(path.glob(pattern)))

def create_folder(path_str: str) -> str:
    """Creates a new folder recursively. Returns absolute path."""
    check, reason = check_path_allowed(path_str)
    if not check:
        raise PermissionError(reason)
        
    path = pathlib.Path(path_str).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return str(path)

def fuzzy_find_file(directory: str, query: str) -> str | None:
    """
    Searches for a file in a directory that matches the query.
    Handles partial names, descriptive words, and case-insensitive matching.
    """
    check, reason = check_path_allowed(directory)
    if not check:
        raise PermissionError(reason)
        
    path = pathlib.Path(directory).expanduser().resolve()
    if not path.is_dir():
        return None
        
    original_query = query.lower().strip()
    # Remove common extensions and filler words to get core keywords
    query = original_query
    for ext in [".mp4", ".mkv", ".avi", ".mov", ".pdf", ".txt", ".docx"]:
        query = query.replace(ext, "")
    for filler in ["play", "movie", "video", "the", "file", "open", "show", "me", "a"]:
        query = query.replace(f" {filler} ", " ").replace(f"{filler} ", "").replace(f" {filler}", "")
    
    query = query.strip()
    if not query:
        return None

    # Strategy 1: Glob match with the cleaned query
    matches = list(path.glob(f"*{query}*"))
    if matches:
        return str(min(matches, key=lambda p: len(p.name)).resolve())
        
    # Strategy 2: Match any word from the query in the filename
    words = [w for w in query.split() if len(w) > 2] # Use words > 2 chars
    if not words: words = query.split() # Fallback to all words
    
    candidates = []
    for f in path.iterdir():
        if f.is_file():
            fname = f.name.lower()
            # If all keywords appear in the filename
            if all(word in fname for word in words):
                candidates.append(f)
    
    if candidates:
        return str(min(candidates, key=lambda p: len(p.name)).resolve())

    # Strategy 3: Just the first word if it's long enough
    if words:
        first_word = words[0]
        matches = list(path.glob(f"{first_word}*"))
        if matches:
            return str(min(matches, key=lambda p: len(p.name)).resolve())
                
    return None
