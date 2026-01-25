# tests/test_ollama_manager.py

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from modules import ollama_manager
import subprocess
import ollama
import os

@pytest.fixture
def mock_config():
    return {
        "ollama_service": {
            "executable_path": "/custom/path/ollama",
            "auto_start_serve": True,
            "ollama_host": "http://localhost",
            "ollama_port": 11434,
            "server_check_retries": 1,
            "server_check_interval_seconds": 0.1
        }
    }

@pytest.fixture
def mock_ui_append():
    return MagicMock()

def setup_manager(config, ui_append):
    # Reset module state
    ollama_manager._is_initialized = False
    ollama_manager._ollama_exe_path_cached = None
    ollama_manager._config_cached = None
    ollama_manager._append_output_func_cached = None
    
    ollama_manager._initialize_manager_if_needed(config, ui_append)

@pytest.mark.asyncio
async def test_find_ollama_executable_configured(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    
    with patch('shutil.which', return_value='/custom/path/ollama'):
        path = await ollama_manager._find_ollama_executable()
        assert path == '/custom/path/ollama'

@pytest.mark.asyncio
async def test_find_ollama_executable_system_path(mock_config, mock_ui_append):
    # Remove config path to test fallback
    mock_config['ollama_service']['executable_path'] = None
    setup_manager(mock_config, mock_ui_append)
    
    with patch('shutil.which', side_effect=lambda x: '/usr/bin/ollama' if x == 'ollama' else None):
        path = await ollama_manager._find_ollama_executable()
        assert path == '/usr/bin/ollama'

@pytest.mark.asyncio
async def test_find_ollama_executable_not_found(mock_config, mock_ui_append):
    mock_config['ollama_service']['executable_path'] = None
    setup_manager(mock_config, mock_ui_append)
    
    with patch('shutil.which', return_value=None):
        path = await ollama_manager._find_ollama_executable()
        assert path is None
        mock_ui_append.assert_called() # Should log error

@pytest.mark.asyncio
async def test_is_ollama_server_running_success(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    
    # Mock ollama.list to succeed (must be run in a thread executor in real code, so we patch to_thread)
    with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = {'models': []}
        
        is_running = await ollama_manager.is_ollama_server_running()
        assert is_running is True

@pytest.mark.asyncio
async def test_is_ollama_server_running_failure(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    
    with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_thread:
        mock_thread.side_effect = ollama.RequestError("Connection refused")
        
        is_running = await ollama_manager.is_ollama_server_running()
        assert is_running is False

@pytest.mark.asyncio
async def test_is_tmux_session_running_true(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    
    mock_process = MagicMock()
    mock_process.returncode = 0
    
    with patch('shutil.which', return_value='/usr/bin/tmux'), \
         patch('asyncio.to_thread', new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = mock_process
        
        is_running = await ollama_manager._is_tmux_session_running("test_session")
        assert is_running is True

@pytest.mark.asyncio
async def test_ensure_ollama_service_already_running(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    
    # Mock executable found and server running
    with patch('modules.ollama_manager._find_ollama_executable', new_callable=AsyncMock) as mock_find, \
         patch('modules.ollama_manager.is_ollama_server_running', new_callable=AsyncMock) as mock_is_running:
        
        mock_find.return_value = "/bin/ollama"
        mock_is_running.return_value = True
        
        ready = await ollama_manager.ensure_ollama_service(mock_config, mock_ui_append)
        assert ready is True
        mock_ui_append.assert_any_call("✅ Ollama server is already running and responsive.", style_class='success')

@pytest.mark.asyncio
async def test_ensure_ollama_service_starts_server(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    
    # Sequence: 
    # 1. _find_ollama_executable -> True
    # 2. is_ollama_server_running -> False (initially)
    # 3. _launch_ollama_serve_in_tmux -> True
    # 4. _wait_for_server_readiness -> checks is_ollama_server_running again -> True
    
    with patch('modules.ollama_manager._find_ollama_executable', new_callable=AsyncMock) as mock_find, \
         patch('modules.ollama_manager.is_ollama_server_running', new_callable=AsyncMock) as mock_is_running, \
         patch('modules.ollama_manager._launch_ollama_serve_in_tmux', new_callable=AsyncMock) as mock_launch, \
         patch('modules.ollama_manager._wait_for_server_readiness', new_callable=AsyncMock) as mock_wait:
        
        mock_find.return_value = "/bin/ollama"
        # First check returns false, triggering launch
        mock_is_running.side_effect = [False, True] 
        mock_launch.return_value = True
        mock_wait.return_value = True
        
        ready = await ollama_manager.ensure_ollama_service(mock_config, mock_ui_append)
        
        assert ready is True
        mock_launch.assert_awaited_once()
        mock_wait.assert_awaited_once()

@pytest.mark.asyncio
async def test_set_ollama_host_from_config(mock_config):
    setup_manager(mock_config, MagicMock())
    
    with patch.dict(os.environ, {}, clear=True):
        ollama_manager.set_ollama_host_from_config(mock_config)
        assert os.environ['OLLAMA_HOST'] == 'http://localhost:11434'
