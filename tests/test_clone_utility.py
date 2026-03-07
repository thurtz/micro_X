# tests/test_clone_utility.py

import pytest
import json
import subprocess
from unittest.mock import mock_open, patch, MagicMock
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

def test_run_command_success():
    """Test successful execution of run_command helper."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="  output  ", check=True)
        result = clone.run_command(["ls"])
        assert result == "output"
        mock_run.assert_called_once_with(["ls"], cwd=None, capture_output=True, text=True, check=True)

def test_run_command_failure():
    """Test failure of run_command helper."""
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd", stderr="error")):
        with pytest.raises(SystemExit) as e:
            clone.run_command(["ls"])
        assert e.value.code == 1

@patch("utils.clone.find_dev_root", return_value="/mock")
@patch("os.path.isdir", return_value=True)
@patch("os.path.exists", return_value=False) # Destination doesn't exist
@patch("os.makedirs")
@patch("utils.clone.run_command")
@patch("builtins.print")
def test_main_success_worktree(mock_print, mock_run, mock_makedirs, mock_exists, mock_isdir, mock_root):
    """Test successful worktree creation."""
    with patch("sys.argv", ["clone.py", "myclone"]):
        clone.main()
        
    # Check that git worktree add was called correctly
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "git" in args
    assert "worktree" in args
    assert "add" in args
    assert "-b" in args
    assert "myclone" in args
    assert any("Clone created successfully" in str(c) for c in mock_print.call_args_list)

@patch("utils.clone.find_dev_root", return_value="/mock")
@patch("os.path.isdir", return_value=True)
@patch("os.path.exists", return_value=True) # Destination ALREADY exists
@patch("builtins.print")
def test_main_already_exists(mock_print, mock_exists, mock_isdir, mock_root):
    """Test error when destination directory already exists."""
    with patch("sys.argv", ["clone.py", "existing"]):
        with pytest.raises(SystemExit) as e:
            clone.main()
        assert e.value.code == 1
    
    assert any("already exists" in str(c) for c in mock_print.call_args_list)
