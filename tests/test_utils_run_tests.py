# tests/test_utils_run_tests.py

import pytest
import os
import subprocess
from unittest.mock import MagicMock, patch, mock_open
from utils import run_tests

@patch("os.path.abspath")
@patch("os.path.dirname")
@patch("os.path.exists")
def test_get_project_root_success(mock_exists, mock_dirname, mock_abspath):
    # Simulate script at /root/utils/run_tests.py
    mock_abspath.return_value = "/root/utils/run_tests.py"
    
    # Use a lambda to simulate dirname behavior to avoid running out of side_effects
    def dirname_side_effect(path):
        if path == "/root/utils/run_tests.py": return "/root/utils"
        if path == "/root/utils": return "/root"
        if path == "/root": return "/"
        return os.path.split(path)[0]
    mock_dirname.side_effect = dirname_side_effect
    
    # Validation checks
    def exists_side_effect(path):
        if path == "/root/main.py": return True
        return False
    mock_exists.side_effect = exists_side_effect
    
    root = run_tests.get_project_root()
    assert root == "/root"

def test_sanitize_pytest_output():
    raw = "Error in /root/project/test.py. User home is /home/user."
    sanitized = run_tests.sanitize_pytest_output(raw, "/root/project", "/home/user")
    assert "<PROJECT_ROOT>/test.py" in sanitized
    assert "User home is <HOME>." in sanitized

def test_display_path():
    proj_root = "/root/project"
    user_home = "/home/user"
    
    # Under project root
    p1 = "/root/project/tests/test_foo.py"
    assert run_tests.display_path(p1, proj_root, user_home) == "<PROJECT_ROOT>/tests/test_foo.py"
    
    # Under home
    p2 = "/home/user/docs/note.txt"
    assert run_tests.display_path(p2, proj_root, user_home) == "<HOME>/docs/note.txt"
    
    # Elsewhere
    p3 = "/tmp/file.txt"
    assert run_tests.display_path(p3, proj_root, user_home) == "/tmp/file.txt"

@patch("utils.run_tests.get_project_root", return_value="/root")
@patch("subprocess.run")
@patch("builtins.open", new_callable=mock_open)
@patch("os.makedirs")
@patch("os.path.exists", return_value=True) # executable exists
@patch("os.path.isdir", return_value=True) # tests dir exists
def test_run_tests_main_logic_success(mock_isdir, mock_exists, mock_makedirs, mock_file, mock_run, mock_get_root):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "Tests passed"
    mock_run.return_value.stderr = ""
    
    exit_code = run_tests.run_tests_main_logic()
    
    assert exit_code == 0
    mock_run.assert_called_once()
    assert mock_file.call_count >= 2

@patch("utils.run_tests.get_project_root", return_value="/root")
@patch("os.makedirs")
@patch("os.path.exists", return_value=False) # Executable missing
def test_run_tests_main_logic_no_pytest(mock_exists, mock_makedirs, mock_get_root, capsys):
    exit_code = run_tests.run_tests_main_logic()
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "Pytest executable not found" in captured.out

@patch("utils.run_tests.get_project_root", return_value="/root")
@patch("os.makedirs")
@patch("os.path.exists", return_value=True)
@patch("os.path.isdir", return_value=False) # Tests dir missing
def test_run_tests_main_logic_no_tests_dir(mock_isdir, mock_exists, mock_makedirs, mock_get_root, capsys):
    exit_code = run_tests.run_tests_main_logic()
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "Tests directory not found" in captured.out
