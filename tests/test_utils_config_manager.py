# tests/test_utils_config_manager.py

import pytest
import os
import json
import socket
import tempfile
from unittest.mock import MagicMock, patch, mock_open
from utils import config_manager
import subprocess
import sys

# --- Helper Tests ---
def test_sanitize_branch_name():
    assert config_manager.sanitize_branch_name_for_tmux("feature/new-ui") == "feature_new-ui"
    assert config_manager.sanitize_branch_name_for_tmux("main") == "main"
    assert config_manager.sanitize_branch_name_for_tmux("user@host:branch") == "user_host_branch"

def test_get_preferred_port():
    base = 8000
    assert config_manager.get_preferred_port_for_branch("main", base) == 8000
    assert config_manager.get_preferred_port_for_branch("dev", base) == 8001
    assert config_manager.get_preferred_port_for_branch("testing", base) == 8002
    # Check that other branches get a deterministic offset
    other_port = config_manager.get_preferred_port_for_branch("feature-x", base)
    assert 8010 <= other_port <= 8019

def test_get_dynamic_tmux_session_name():
    name = config_manager.get_dynamic_tmux_session_name("dev")
    assert name == "microx_config_server_session_dev"

# --- HTTP Handler Tests ---
@pytest.fixture
def mock_request_handler():
    # Helper to instantiate the handler with mocked request/client_address/server
    def _create_handler(request_body, path):
        request = MagicMock()
        client_address = ('127.0.0.1', 12345)
        server = MagicMock()
        
        # Mock the rfile (read stream)
        request.makefile.return_value.read.return_value = request_body.encode('utf-8')
        # We need to mock rfile on the handler instance itself because SimpleHTTPRequestHandler uses it
        
        # We'll patch SimpleHTTPRequestHandler's __init__ to avoid socket setup
        with patch('http.server.SimpleHTTPRequestHandler.__init__', return_value=None) as mock_init:
            handler = config_manager.ConfigManagerHTTPRequestHandler(request, client_address, server)
            # Manually set attributes normally set by __init__ or parse_request
            handler.client_address = client_address
            handler.path = path
            handler.command = "POST"
            handler.request_version = "HTTP/1.1"
            handler.requestline = f"POST {path} HTTP/1.1"
            handler.close_connection = True
            handler.headers = {'Content-Length': str(len(request_body))}
            handler.rfile = MagicMock()
            handler.rfile.read.return_value = request_body.encode('utf-8')
            handler.wfile = MagicMock()
            handler.send_response = MagicMock()
            return handler
    return _create_handler

def test_do_post_save_user_config(mock_request_handler):
    with tempfile.TemporaryDirectory() as tmpdir:
        config_manager.ConfigManagerHTTPRequestHandler.PROJECT_ROOT_PATH = tmpdir
        
        data = {"theme": "dark"}
        handler = mock_request_handler(json.dumps(data), '/api/save/user_config')
        
        handler.do_POST()
        
        # Check response code (we mock send_response)
        handler.send_response.assert_called_with(200)
        
        # Verify file written
        expected_path = os.path.join(tmpdir, "config", "user_config.json")
        assert os.path.exists(expected_path)
        with open(expected_path, 'r') as f:
            saved_data = json.load(f)
        assert saved_data == data

def test_do_post_invalid_json(mock_request_handler):
    handler = mock_request_handler("{invalid-json", '/api/save/user_config')
    handler.do_POST()
    handler.send_response.assert_called_with(400)

def test_do_post_invalid_endpoint(mock_request_handler):
    handler = mock_request_handler("{}", '/api/save/unknown')
    handler.do_POST()
    handler.send_response.assert_called_with(404)

# --- Server Management Tests ---
@patch("subprocess.run")
def test_is_tmux_session_running(mock_run):
    # Case: Running
    mock_run.return_value.returncode = 0
    assert config_manager.is_tmux_session_running("sess") is True
    
    # Case: Not running
    mock_run.return_value.returncode = 1
    assert config_manager.is_tmux_session_running("sess") is False
    
    # Case: Tmux missing
    mock_run.side_effect = FileNotFoundError
    assert config_manager.is_tmux_session_running("sess") is False

@patch("utils.config_manager.is_tmux_session_running")
@patch("subprocess.run")
@patch("webbrowser.open_new_tab")
@patch("utils.config_manager.find_free_port")
@patch("time.sleep") # Speed up test
def test_start_server_in_tmux_new(mock_sleep, mock_find_port, mock_browser, mock_run, mock_is_running):
    # Setup
    mock_is_running.return_value = False # Not running
    mock_find_port.return_value = 8123
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the HTML file so the check passes
        os.makedirs(os.path.join(tmpdir, "tools", "config_manager"), exist_ok=True)
        with open(os.path.join(tmpdir, "tools", "config_manager", "index.html"), 'w') as f:
            f.write("<html></html>")
            
        config_manager.start_server_in_tmux(8000, tmpdir, "dev")
        
        # Verify tmux command
        assert mock_run.called
        args = mock_run.call_args[0][0]
        assert args[0] == "tmux"
        assert args[1] == "new-session"
        assert "microx_config_server_session_dev" in args
        
        # Verify browser opened
        mock_browser.assert_called_with("http://localhost:8123/tools/config_manager/index.html")

@patch("utils.config_manager.is_tmux_session_running")
@patch("subprocess.run")
def test_stop_server_tmux_session(mock_run, mock_is_running):
    mock_is_running.return_value = True
    
    config_manager.stop_server_tmux_session("dev")
    
    assert mock_run.called
    args = mock_run.call_args[0][0]
    assert args == ["tmux", "kill-session", "-t", "microx_config_server_session_dev"]

@patch("utils.config_manager.get_project_root")
@patch("utils.config_manager.get_current_branch")
@patch("utils.config_manager.start_server_in_tmux")
def test_main_start_flag(mock_start_server, mock_get_branch, mock_get_root):
    mock_get_root.return_value = "/root"
    mock_get_branch.return_value = "main"
    
    # Mock sys.argv
    with patch.object(sys, 'argv', ['prog', '--start']):
        config_manager.main()
        
    mock_start_server.assert_called()

