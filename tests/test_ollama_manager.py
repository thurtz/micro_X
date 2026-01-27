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
    ollama_manager._is_initialized = False
    ollama_manager._ollama_exe_path_cached = None
    ollama_manager._config_cached = None
    ollama_manager._append_output_func_cached = None
    ollama_manager._initialize_manager_if_needed(config, ui_append)

@pytest.mark.asyncio
async def test_find_ollama_executable_configured(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    with patch('shutil.which', return_value='/custom/path/ollama'):
        assert await ollama_manager._find_ollama_executable() == '/custom/path/ollama'

@pytest.mark.asyncio
async def test_is_ollama_server_running_success(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_thread:
        mock_thread.return_value = {'models': []}
        assert await ollama_manager.is_ollama_server_running() is True

@pytest.mark.asyncio
async def test_ensure_ollama_service_starts_server(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    with patch('modules.ollama_manager._find_ollama_executable', new_callable=AsyncMock) as mock_find, \
         patch('modules.ollama_manager.is_ollama_server_running', new_callable=AsyncMock) as mock_is_running, \
         patch('modules.ollama_manager._launch_ollama_serve_in_tmux', new_callable=AsyncMock) as mock_launch, \
         patch('modules.ollama_manager._wait_for_server_readiness', new_callable=AsyncMock) as mock_wait:
        
        mock_find.return_value = "/bin/ollama"
        mock_is_running.side_effect = [False, True] 
        mock_launch.return_value = True
        mock_wait.return_value = True
        
        assert await ollama_manager.ensure_ollama_service(mock_config, mock_ui_append) is True
        mock_launch.assert_awaited_once()

@pytest.mark.asyncio
async def test_explicit_stop_ollama_service_not_running(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    with patch('shutil.which', return_value='/bin/tmux'), \
         patch('modules.ollama_manager._is_tmux_session_running', new_callable=AsyncMock) as mock_running, \
         patch('modules.ollama_manager.is_ollama_server_running', new_callable=AsyncMock) as mock_server:
        
        mock_running.return_value = False
        mock_server.return_value = False
        
        assert await ollama_manager.explicit_stop_ollama_service(mock_config, mock_ui_append) is True
        mock_ui_append.assert_any_call("   No other Ollama server appears to be running.", style_class='info')

@pytest.mark.asyncio
async def test_explicit_stop_ollama_service_external_running(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    with patch('shutil.which', return_value='/bin/tmux'), \
         patch('modules.ollama_manager._is_tmux_session_running', new_callable=AsyncMock) as mock_running, \
         patch('modules.ollama_manager.is_ollama_server_running', new_callable=AsyncMock) as mock_server:
        
        mock_running.return_value = False
        mock_server.return_value = True # External server
        
        assert await ollama_manager.explicit_stop_ollama_service(mock_config, mock_ui_append) is True
        mock_ui_append.assert_any_call("   However, an Ollama server is currently responsive (possibly started externally).", style_class='warning')

@pytest.mark.asyncio
async def test_get_ollama_status_info(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    with patch('modules.ollama_manager._find_ollama_executable', new_callable=AsyncMock) as mock_find, \
         patch('modules.ollama_manager.is_ollama_server_running', new_callable=AsyncMock) as mock_is_running, \
         patch('modules.ollama_manager._is_tmux_session_running', new_callable=AsyncMock) as mock_is_tmux:
        
        mock_find.return_value = "/bin/ollama"
        mock_is_running.return_value = True
        mock_is_tmux.return_value = True
        
        await ollama_manager.get_ollama_status_info(mock_config, mock_ui_append)
        
        calls = [str(c) for c in mock_ui_append.call_args_list]
        assert any("Ollama Executable: Found" in c for c in calls)
        assert any("Ollama Server API: Responsive" in c for c in calls)
        assert any("Managed Tmux Session" in c for c in calls)

@pytest.mark.asyncio
async def test_set_ollama_host_from_config(mock_config):
    setup_manager(mock_config, MagicMock())
    with patch.dict(os.environ, {}, clear=True):
        ollama_manager.set_ollama_host_from_config(mock_config)
        assert os.environ['OLLAMA_HOST'] == 'http://localhost:11434'

def test_set_ollama_host_formatting(mock_config):
    # Test host without scheme
    mock_config['ollama_service']['ollama_host'] = "127.0.0.1"
    with patch.dict(os.environ, {}, clear=True):
        ollama_manager.set_ollama_host_from_config(mock_config)
        assert os.environ['OLLAMA_HOST'] == 'http://127.0.0.1:11434'

@pytest.mark.asyncio
async def test_find_ollama_executable_not_initialized(mock_ui_append):
    ollama_manager._is_initialized = False
    assert await ollama_manager._find_ollama_executable() is None

@pytest.mark.asyncio
async def test_find_ollama_executable_fallback(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    # Configured path invalid, system path valid
    mock_config['ollama_service']['executable_path'] = "/invalid/path"
    
    with patch('shutil.which') as mock_which:
        def side_effect(path):
            if path == "/invalid/path": return None
            if path == "ollama": return "/usr/bin/ollama"
            return None
        mock_which.side_effect = side_effect
        
        assert await ollama_manager._find_ollama_executable() == "/usr/bin/ollama"

@pytest.mark.asyncio
async def test_find_ollama_executable_none(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    mock_config['ollama_service']['executable_path'] = None
    with patch('shutil.which', return_value=None):
        assert await ollama_manager._find_ollama_executable() is None
        mock_ui_append.assert_any_call("❌ Ollama executable ('ollama') not found in your system PATH.", style_class='error')

@pytest.mark.asyncio
async def test_is_ollama_server_running_errors(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    
    # RequestError
    with patch('asyncio.to_thread', side_effect=ollama.RequestError("Connection refused")):
        assert await ollama_manager.is_ollama_server_running() is False
        
    # General Exception
    with patch('asyncio.to_thread', side_effect=Exception("Boom")):
        assert await ollama_manager.is_ollama_server_running() is False
        mock_ui_append.assert_any_call("⚠️ Error checking Ollama status: Boom", style_class='warning')

@pytest.mark.asyncio
async def test_launch_ollama_serve_errors(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    # Mock find executable success
    ollama_manager._ollama_exe_path_cached = "/bin/ollama"
    
    # Tmux missing
    with patch('shutil.which', return_value=None):
        assert await ollama_manager._launch_ollama_serve_in_tmux() is False
        mock_ui_append.assert_any_call("❌ tmux not found. Cannot automatically start 'ollama serve'.", style_class='error')

    # Launch failure (CalledProcessError)
    with patch('shutil.which', return_value='/bin/tmux'), \
         patch('modules.ollama_manager._is_tmux_session_running', new_callable=AsyncMock, return_value=False), \
         patch('asyncio.to_thread', side_effect=subprocess.CalledProcessError(1, "cmd", stderr="Start failed")):
        
        assert await ollama_manager._launch_ollama_serve_in_tmux() is False
        # Use str(c) to check call args content loosely or assert_any_call if exact match known
        calls = [str(c) for c in mock_ui_append.call_args_list]
        assert any("Start failed" in c for c in calls)

@pytest.mark.asyncio
async def test_wait_for_server_readiness_failure(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    mock_config['ollama_service']['server_check_retries'] = 2
    mock_config['ollama_service']['server_check_interval_seconds'] = 0.01
    
    with patch('modules.ollama_manager.is_ollama_server_running', new_callable=AsyncMock, return_value=False):
        assert await ollama_manager._wait_for_server_readiness() is False
        mock_ui_append.assert_any_call("❌ Ollama server did not become responsive in time.", style_class='error')

@pytest.mark.asyncio
async def test_explicit_stop_errors(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    
    # Tmux missing
    with patch('shutil.which', return_value=None):
        assert await ollama_manager.explicit_stop_ollama_service(mock_config, mock_ui_append) is False
        
    # Kill failure
    with patch('shutil.which', return_value='/bin/tmux'), \
         patch('modules.ollama_manager._is_tmux_session_running', new_callable=AsyncMock, return_value=True), \
         patch('asyncio.to_thread', side_effect=subprocess.CalledProcessError(1, "kill", stderr="Kill failed")):
         
        assert await ollama_manager.explicit_stop_ollama_service(mock_config, mock_ui_append) is False
        calls = [str(c) for c in mock_ui_append.call_args_list]
        assert any("Kill failed" in c for c in calls)

@pytest.mark.asyncio
async def test_explicit_restart_success(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    
    with patch('modules.ollama_manager.explicit_stop_ollama_service', new_callable=AsyncMock, return_value=True) as mock_stop, \
         patch('modules.ollama_manager.explicit_start_ollama_service', new_callable=AsyncMock, return_value=True) as mock_start:
         
         assert await ollama_manager.explicit_restart_ollama_service(mock_config, mock_ui_append) is True
         mock_stop.assert_awaited_once()
         mock_start.assert_awaited_once()

@pytest.mark.asyncio
async def test_explicit_restart_fail_stop(mock_config, mock_ui_append):
    setup_manager(mock_config, mock_ui_append)
    
    with patch('modules.ollama_manager.explicit_stop_ollama_service', new_callable=AsyncMock, return_value=False):
         assert await ollama_manager.explicit_restart_ollama_service(mock_config, mock_ui_append) is False
         mock_ui_append.assert_any_call("❌ Restart aborted because stopping the service failed critically.", style_class='error')