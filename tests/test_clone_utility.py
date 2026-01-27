# tests/test_clone_utility.py

import pytest
import json
from unittest.mock import mock_open, patch
from utils import clone

def test_get_next_version_name_success():
    """Test standard version increment."""
    mock_config = json.dumps({"application": {"version": "0.0.1034"}})
    with patch("builtins.open", mock_open(read_data=mock_config)):
        name = clone.get_next_version_name("/dummy/root")
        assert name == "clone_v0.0.1035"

def test_get_next_version_name_short_version():
    """Test fallback when version string is short."""
    mock_config = json.dumps({"application": {"version": "1.0"}})
    with patch("builtins.open", mock_open(read_data=mock_config)):
        name = clone.get_next_version_name("/dummy/root")
        assert name == "clone_v1.0_next"

def test_get_next_version_name_file_not_found():
    """Test handling of missing config file."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        name = clone.get_next_version_name("/dummy/root")
        assert name is None

def test_get_next_version_name_invalid_json():
    """Test handling of invalid JSON."""
    with patch("builtins.open", mock_open(read_data="{invalid_json")):
        name = clone.get_next_version_name("/dummy/root")
        assert name is None

# --- New Expansion Tests ---

def test_parse_gitignore(tmp_path):
    # Create dummy gitignore
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.log\n# comment\ndist/\n")
    
    patterns = clone.parse_gitignore(str(tmp_path))
    
    assert "*.log" in patterns
    assert "dist/" in patterns
    assert "# comment" not in patterns
    # Core ignores
    assert ".git" in patterns
    assert "clones" in patterns

def test_should_ignore():
    root = "/root"
    patterns = ["*.log", "dist/", "secret.txt"]
    
    # Ignore file by pattern
    assert "file.log" in clone.should_ignore("/root", ["file.log", "main.py"], root, patterns)
    
    # Ignore dir by pattern
    assert "dist" in clone.should_ignore("/root", ["dist", "src"], root, patterns)
    
    # Ignore file in subdir
    assert "secret.txt" in clone.should_ignore("/root/subdir", ["secret.txt", "readme.md"], root, patterns)
    
    # Don't ignore normal files
    assert not clone.should_ignore("/root", ["main.py"], root, patterns)

@patch("utils.clone.find_micro_x_root", return_value="/mock")
@patch("os.path.isdir", return_value=True)
@patch("os.path.exists", return_value=False) # Destination doesn't exist
@patch("shutil.copytree")
@patch("os.makedirs")
@patch("builtins.print")
def test_main_success(mock_print, mock_makedirs, mock_copytree, mock_exists, mock_isdir, mock_root):
    with patch("sys.argv", ["clone.py", "myclone"]):
        clone.main()
        
    mock_copytree.assert_called_once()
    # Check destination path
    assert "myclone" in mock_copytree.call_args[0][1]
    assert any("Clone created successfully" in str(c) for c in mock_print.call_args_list)

@patch("utils.clone.find_micro_x_root", return_value="/mock")
@patch("os.path.isdir", return_value=True)
@patch("os.path.exists", return_value=True) # Destination ALREADY exists
@patch("builtins.print")
def test_main_already_exists(mock_print, mock_exists, mock_isdir, mock_root):
    with patch("sys.argv", ["clone.py", "existing"]):
        with pytest.raises(SystemExit) as e:
            clone.main()
        assert e.value.code == 1
    
    assert any("already exists" in str(c) for c in mock_print.call_args_list)

