# tests/test_utils_generate_snapshot.py

import pytest
import os
import re
import datetime
from unittest.mock import MagicMock, patch, mock_open
from utils import generate_snapshot

@patch("os.path.exists", return_value=True)
@patch("os.path.isdir", return_value=True)
def test_get_project_root(mock_isdir, mock_exists):
    # Mocking __file__ on the module object
    with patch.object(generate_snapshot, "__file__", "/root/utils/generate_snapshot.py"):
        root = generate_snapshot.get_project_root()
        # Logic: abspath(__file__) -> /root/utils/generate_snapshot.py
        # dirname -> /root/utils
        # dirname -> /root
        # checks existence of /root/main.py etc (mocked True)
        assert root == "/root"

def test_extract_api_documentation_success():
    code = 'def foo():\n    """Docstring."""\n    pass'
    with patch("builtins.open", mock_open(read_data=code)):
        docs = generate_snapshot.extract_api_documentation("dummy.py")
        assert "Function: foo" in docs
        assert "Docstring." in docs

def test_extract_api_documentation_syntax_error():
    code = 'def foo(' # Invalid syntax
    with patch("builtins.open", mock_open(read_data=code)):
        docs = generate_snapshot.extract_api_documentation("dummy.py")
        assert "[Syntax error parsing dummy.py" in docs

@patch("subprocess.run")
def test_run_utility_script_success(mock_run):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "Output"
    
    with patch("os.path.exists", return_value=True):
        result = generate_snapshot.run_utility_script("test.py", "/root", "/root/utils")
        assert result["success"] is True
        assert result["test_status"] == "not_run"

@patch("subprocess.run")
def test_run_utility_script_test_fail(mock_run):
    mock_run.return_value.returncode = 1
    
    with patch("os.path.exists", return_value=True):
        result = generate_snapshot.run_utility_script("run_tests.py", "/root", "/root/utils")
        assert result["success"] is True # Script ran, just tests failed
        assert result["test_status"] == "failed"

def test_get_message_from_log_line():
    line = "2024-01-01 10:00:00,000 - INFO - module:123 -   Hello World  "
    msg = generate_snapshot._get_message_from_log_line(line)
    assert msg == "Hello World"

def test_get_last_log_session_none():
    with patch("builtins.open", mock_open(read_data="")):
        with patch("os.path.exists", return_value=True):
            status, content = generate_snapshot._get_last_log_session("log.log")
            assert status == "NONE"

@patch("utils.generate_snapshot.get_project_root", return_value="/root")
@patch("utils.generate_snapshot.run_utility_script")
@patch("utils.generate_snapshot._get_last_log_session")
@patch("builtins.open", new_callable=mock_open)
@patch("os.makedirs")
def test_generate_snapshot_success(mock_makedirs, mock_file, mock_get_log, mock_run_util, mock_get_root):
    mock_run_util.return_value = {"success": True, "message": "", "test_status": "passed"}
    mock_get_log.return_value = ("NONE", "")
    
    path, status = generate_snapshot.generate_snapshot("Summary", include_logs=False)
    
    assert "micro_x_context_snapshot" in path
    assert status == "passed"
    mock_file.assert_called()
