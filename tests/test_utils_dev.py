# tests/test_utils_dev.py

import pytest
import os
import subprocess
from unittest.mock import MagicMock, patch, mock_open
from utils import dev

@pytest.fixture
def mock_root():
    return "/mock/root"

def test_find_environment_root_success(mocker, mock_root):
    # Setup path structure simulation
    # We want start at /mock/root/utils
    start_path = f"{mock_root}/utils"
    
    # We mock abspath to just return the argument (simplification)
    mocker.patch("os.path.abspath", side_effect=lambda p: p)
    # We mock dirname to strip last component
    mocker.patch("os.path.dirname", side_effect=lambda p: os.path.split(p)[0])
    
    # We need to control where 'main.py' is found.
    # It should be found at /mock/root/main.py
    # but NOT at /mock/root/utils/main.py
    
    def isfile_side_effect(path):
        return path == f"{mock_root}/main.py"

    def isdir_side_effect(path):
        # Allow dirs for testing/dev branches at root
        if path.startswith(f"{mock_root}/micro_X-"):
            return True
        return False

    mocker.patch("os.path.isfile", side_effect=isfile_side_effect)
    mocker.patch("os.path.isdir", side_effect=isdir_side_effect)
    
    # Mock __file__ is tricky. 
    # Instead, let's patch where it's used: os.path.dirname(__file__)
    # find_environment_root calls: current_path = os.path.abspath(os.path.dirname(__file__))
    # effectively: current_path = start_location
    
    # We can patch os.path.dirname to return start_path ONLY for the first call?
    # Or just patch the logic inside find_environment_root? No, we want to test logic.
    
    # Let's rely on the fact that we can patch dev.__file__ if we imported it
    mocker.patch.object(dev, "__file__", f"{start_path}/dev.py")
    
    root = dev.find_environment_root()
    assert root == mock_root

def test_find_environment_root_fail(mocker, mock_root):
    mocker.patch("os.path.abspath", return_value=f"{mock_root}/utils/dev.py")
    mocker.patch("os.path.dirname", side_effect=lambda p: os.path.split(p)[0])
    mocker.patch("os.path.isfile", return_value=False) # main.py missing
    
    root = dev.find_environment_root()
    assert root is None

def test_load_configuration_defaults(mocker, mock_root):
    mock_config = {"integrity_check": {"allowed": ["main"]}}
    mock_json_load = mocker.patch("json.load", return_value=mock_config)
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open())
    
    config = dev.load_configuration(mock_root)
    assert config == mock_config

def test_run_command_success(mocker):
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value.returncode = 0
    
    success = dev.run_command(["ls", "-l"], "/tmp", "Listing")
    assert success is True
    mock_subprocess.assert_called_once()

def test_run_command_fail(mocker):
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.side_effect = subprocess.CalledProcessError(1, ["ls"])
    
    success = dev.run_command(["ls", "-l"], "/tmp", "Listing")
    assert success is None

def test_update_single_branch(mocker, mock_root):
    mock_run = mocker.patch("utils.dev.run_command")
    mocker.patch("os.path.isdir", return_value=True)
    
    dev.update_single_branch(mock_root, "dev", "micro_X-dev")
    
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == ['git', 'pull', 'origin', 'dev']

def test_snapshot_for_branch(mocker, mock_root):
    mock_run = mocker.patch("utils.dev.run_command")
    mock_run.return_value = "Successfully generated snapshot: /tmp/snap.txt"
    mocker.patch("os.path.isdir", return_value=True)
    mocker.patch("os.path.isfile", return_value=True)
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("shutil.move")
    
    dev.snapshot_for_branch(mock_root, "dev", f"{mock_root}/micro_X-dev", [])
    
    mock_run.assert_called_once()
    assert "generate_snapshot.py" in mock_run.call_args[0][0][1]

def test_update_docs(mocker, mock_root):
    mock_run = mocker.patch("utils.dev.run_command")
    mock_run.return_value = True
    mocker.patch("os.path.isdir", return_value=True)
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("shutil.copy2")
    
    dev.update_docs(mock_root)
    
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == ['make', '-C', f'{mock_root}/{dev.DEV_BRANCH_DIR_NAME}/docs/source', 'html']
