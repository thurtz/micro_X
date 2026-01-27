# tests/test_utils_update.py

import pytest
import os
import subprocess
from unittest.mock import MagicMock, patch, mock_open
from utils import update

@patch("os.path.abspath")
@patch("os.path.dirname")
@patch("os.path.exists")
def test_get_project_root(mock_exists, mock_dirname, mock_abspath):
    mock_abspath.return_value = "/root/utils/update.py"
    # Logic: dirname(/root/utils/update.py) -> /root/utils
    # dirname(/root/utils) -> /root
    mock_dirname.side_effect = ["/root/utils", "/root"]
    mock_exists.return_value = True
    
    root = update.get_project_root()
    assert root == "/root"

def test_get_file_hash_success():
    with patch("builtins.open", mock_open(read_data=b"content")):
        with patch("os.path.exists", return_value=True):
            hash_val = update.get_file_hash("dummy")
            # sha256 of "content"
            assert len(hash_val) == 64

def test_get_file_hash_missing():
    with patch("os.path.exists", return_value=False):
        assert update.get_file_hash("missing") is None

@patch("shutil.which")
@patch("subprocess.run")
@patch("utils.update.get_project_root", return_value="/root")
@patch("utils.update.get_file_hash")
@patch("builtins.print")
def test_run_update_success(mock_print, mock_hash, mock_root_func, mock_run, mock_which):
    mock_which.return_value = "/bin/git"
    
    # Hashes match (no reqs change)
    mock_hash.return_value = "hash123"
    
    # Mock git rev-parse output
    mock_rev_parse = MagicMock()
    mock_rev_parse.stdout = "dev\n"
    
    # Mock git pull output
    mock_pull = MagicMock()
    mock_pull.returncode = 0
    mock_pull.stdout = "Updating..."
    
    mock_run.side_effect = [mock_rev_parse, mock_pull]
    
    update.run_update()
    
    # Verify sequence
    assert mock_run.call_count == 2
    mock_run.assert_any_call(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
        cwd="/root", capture_output=True, text=True, check=True, errors='replace'
    )
    mock_run.assert_any_call(
        ['git', 'pull', 'origin', 'dev'],
        cwd="/root", capture_output=True, text=True, errors='replace'
    )
    
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("Git pull successful" in c for c in calls)

@patch("shutil.which")
@patch("builtins.print")
def test_run_update_no_git(mock_print, mock_which):
    mock_which.return_value = None
    update.run_update()
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("git' command not found" in str(c) for c in calls)
