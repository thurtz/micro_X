# tests/test_utils_logs.py

import pytest
import os
import subprocess
from unittest.mock import MagicMock, patch
from utils import logs

@patch("subprocess.run")
def test_get_current_branch_success(mock_run):
    mock_run.return_value.stdout = "dev\n"
    branch = logs.get_current_branch()
    assert branch == "dev"

@patch("subprocess.run")
def test_get_current_branch_fail(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, ["git"])
    branch = logs.get_current_branch()
    assert branch is None

@patch("utils.logs.get_current_branch")
@patch("subprocess.run")
@patch("builtins.print")
@patch("os.path.exists", return_value=True)
def test_main_default_dev(mock_exists, mock_print, mock_run, mock_get_branch):
    mock_get_branch.return_value = "dev"
    with patch("sys.argv", ["logs.py"]):
        logs.main()
    
    args = mock_run.call_args[0][0]
    assert args[0] == "tail"
    assert "micro_X-dev/logs/micro_x.log" in args[2]

@patch("subprocess.run")
@patch("builtins.print")
@patch("os.path.exists", return_value=True)
def test_main_flag_main(mock_exists, mock_print, mock_run):
    with patch("sys.argv", ["logs.py", "--main"]):
        logs.main()
    
    args = mock_run.call_args[0][0]
    # Check that it points to the root logs (not micro_X-main, but just ROOT/logs)
    assert args[2].endswith("/micro_X/logs/micro_x.log")

@patch("utils.logs.get_current_branch")
@patch("subprocess.run")
@patch("builtins.print")
@patch("os.path.exists", return_value=True)
def test_main_fallback_to_dev(mock_exists, mock_print, mock_run, mock_get_branch):
    # Current branch is "feature-x", not a primary branch
    mock_get_branch.return_value = "feature-x"
    with patch("sys.argv", ["logs.py"]):
        logs.main()
        
    # Should default to dev
    args = mock_run.call_args[0][0]
    assert "micro_X-dev" in args[2]
    
    # Check for info message
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("Defaulting to 'dev' logs" in str(c) for c in calls)

@patch("os.path.exists", return_value=False)
@patch("builtins.print")
def test_main_log_file_not_found(mock_print, mock_exists):
    with patch("sys.argv", ["logs.py", "--dev"]):
        with pytest.raises(SystemExit) as e:
            logs.main()
        assert e.value.code == 1
    
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("Log file not found" in str(c) for c in calls)
