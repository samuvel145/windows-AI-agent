import pytest
import pathlib
from amdea.execution import filesystem
from amdea import config

@pytest.fixture
def mock_allowed_roots(tmp_path, monkeypatch):
    """Sets ALLOWED_ROOTS to tmp_path for isolated testing."""
    root = tmp_path / "amdea_test"
    root.mkdir()
    monkeypatch.setattr(config, "ALLOWED_ROOTS", [root])
    return root

def test_create_and_read_file(mock_allowed_roots):
    fpath = str(mock_allowed_roots / "test.txt")
    filesystem.create_file(fpath, "hello world")
    content = filesystem.read_file(fpath)
    assert content == "hello world"

def test_create_file_creates_parents(mock_allowed_roots):
    fpath = str(mock_allowed_roots / "subdir" / "nested.txt")
    filesystem.create_file(fpath, "nested")
    assert pathlib.Path(fpath).exists()

def test_delete_file(mock_allowed_roots):
    fpath = str(mock_allowed_roots / "kill.me")
    filesystem.create_file(fpath)
    assert filesystem.delete_file(fpath) is True
    assert not pathlib.Path(fpath).exists()

def test_list_folder_metadata(mock_allowed_roots):
    filesystem.create_file(str(mock_allowed_roots / "a.txt"), "A")
    filesystem.create_folder(str(mock_allowed_roots / "sub"))
    
    items = filesystem.list_folder(str(mock_allowed_roots))
    assert len(items) == 2
    names = [i["name"] for i in items]
    assert "a.txt" in names
    assert "sub" in names
    
    sub = next(i for i in items if i["name"] == "sub")
    assert sub["is_dir"] is True

def test_path_outside_roots_blocked(mock_allowed_roots):
    with pytest.raises(PermissionError):
        filesystem.read_file("/etc/passwd")

def test_delete_glob(mock_allowed_roots):
    filesystem.create_file(str(mock_allowed_roots / "test1.log"))
    filesystem.create_file(str(mock_allowed_roots / "test2.log"))
    filesystem.create_file(str(mock_allowed_roots / "keep.txt"))
    
    deleted = filesystem.delete_files_glob(str(mock_allowed_roots), "*.log")
    assert len(deleted) == 2
    assert not (mock_allowed_roots / "test1.log").exists()
    assert (mock_allowed_roots / "keep.txt").exists()
