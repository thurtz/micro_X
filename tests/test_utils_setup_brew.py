# tests/test_utils_setup_brew.py

import pytest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os
from utils import setup_brew

@patch("shutil.which")
def test_command_exists(mock_which):
    mock_which.return_value = "/bin/ls"
    assert setup_brew.command_exists("ls") is True
    
    mock_which.return_value = None
    assert setup_brew.command_exists("unknown") is False

def test_is_wsl_env():
    with patch.dict(os.environ, {"WSL_DISTRO_NAME": "Ubuntu"}):
        assert setup_brew.is_wsl() is True

def test_is_wsl_proc():
    # Clear env for this test to ensure it falls back to /proc
    with patch.dict(os.environ, {}, clear=True):
        with patch("builtins.open", mock_open(read_data="Linux version ... Microsoft ...")):
            assert setup_brew.is_wsl() is True

@patch("utils.setup_brew.command_exists", return_value=True)
@patch("builtins.print")
def test_install_homebrew_already_installed(mock_print, mock_exists):
    assert setup_brew.install_homebrew() is True
    mock_print.assert_called_with("✅ Homebrew is already installed.")

@patch("utils.setup_brew.command_exists", return_value=False)
@patch("subprocess.run")
def test_install_homebrew_install_macos(mock_run, mock_exists):
    with patch("sys.platform", "darwin"):
        mock_run.return_value.returncode = 0
        assert setup_brew.install_homebrew() is True
        mock_run.assert_called_once()
