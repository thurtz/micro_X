# tests/test_utils_git_branch.py

import pytest
from unittest.mock import MagicMock, patch
import subprocess
from utils import git_branch

@patch("builtins.print")
@patch("subprocess.run")
def test_get_current_branch_success(mock_run, mock_print):
    mock_run.return_value.stdout = "feature-branch\n"
    git_branch.get_current_branch()
    mock_print.assert_called_with("Current Git Branch: feature-branch")

@patch("subprocess.run")
def test_get_current_branch_git_not_found(mock_run):
    mock_run.side_effect = FileNotFoundError
    with pytest.raises(SystemExit) as e:
        git_branch.get_current_branch()
    assert e.value.code == 1

@patch("subprocess.run")
def test_get_current_branch_error(mock_run):
    error = subprocess.CalledProcessError(1, ["git"])
    error.stderr = "fatal: not a git repository"
    mock_run.side_effect = error
    with pytest.raises(SystemExit) as e:
        git_branch.get_current_branch()
    assert e.value.code == 1
