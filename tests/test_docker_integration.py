import pytest
import os
from unittest.mock import MagicMock, patch, AsyncMock
from modules.shell_engine import ShellEngine

@pytest.fixture
def mock_config():
    return {
        "ollama_service": {"ollama_host": "localhost", "ollama_port": 11434},
        "behavior": {"default_category_for_unclassified": "simple"},
        "security": {"dangerous_patterns": [], "warn_on_commands": []},
        "ai_models": {},
        "timeouts": {"tmux_poll_seconds": 1, "tmux_semi_interactive_sleep_seconds": 0.1},
        "ui": {},
        "paths": {"tmux_log_base_path": "/tmp"}
    }

@pytest.fixture
def shell_engine(mock_config):
    ui_manager = MagicMock()
    # Mock router agent creation to avoid LangChain imports during engine init
    with patch('modules.shell_engine.create_router_agent', return_value=MagicMock()):
        engine = ShellEngine(mock_config, ui_manager)
    return engine

def test_breakout_mode_detection(mock_config):
    """Test that DOCKER_BREAKOUT env var correctly enables breakout mode."""
    with patch.dict(os.environ, {"DOCKER_BREAKOUT": "true"}):
        with patch('modules.shell_engine.create_router_agent', return_value=MagicMock()):
            engine = ShellEngine(mock_config, MagicMock())
            assert engine._is_in_docker_breakout is True

    with patch.dict(os.environ, {"DOCKER_BREAKOUT": "false"}):
        with patch('modules.shell_engine.create_router_agent', return_value=MagicMock()):
            engine = ShellEngine(mock_config, MagicMock())
            assert engine._is_in_docker_breakout is False

def test_apply_host_breakout_basic(shell_engine):
    """Test that basic commands breakout via chroot when in breakout mode."""
    shell_engine._is_in_docker_breakout = True
    shell_engine.current_directory = "/home/user/project"
    
    cmd = "ls -l"
    result = shell_engine._apply_host_breakout(cmd)
    
    assert "chroot /host" in result
    assert "cd /home/user/project" in result
    assert "ls -l" in result

def test_apply_host_breakout_internal_commands(shell_engine):
    """Test that internal micro_X commands do NOT breakout."""
    shell_engine._is_in_docker_breakout = True
    
    # Internal aliases start with /
    cmd = "/help"
    result = shell_engine._apply_host_breakout(cmd)
    assert result == "/help"
    
    # Internal project scripts
    cmd = "python3 main.py"
    result = shell_engine._apply_host_breakout(cmd)
    assert result == "python3 main.py"

def test_apply_host_breakout_forced_bang(shell_engine):
    """Test that commands prefixed with '!' always breakout and strip the prefix."""
    shell_engine._is_in_docker_breakout = True
    
    # Scenario 1: Bang in the command string itself
    cmd = "!ls"
    result = shell_engine._apply_host_breakout(cmd)
    assert "chroot /host" in result
    assert "ls" in result
    assert "!" not in result

    # Scenario 2: Bang in the original input display
    cmd = "ls"
    original_input = "!ls"
    result = shell_engine._apply_host_breakout(cmd, original_input)
    assert "chroot /host" in result
    assert "ls" in result

@pytest.mark.asyncio
async def test_execute_shell_command_breakout_integration(shell_engine):
    """Integration test for execute_shell_command applying breakout."""
    shell_engine._is_in_docker_breakout = True
    shell_engine.current_directory = "/app"
    
    with patch("asyncio.create_subprocess_shell") as mock_subproc:
        mock_subproc.return_value = MagicMock(wait=AsyncMock(return_value=0), returncode=0)
        
        await shell_engine.execute_shell_command("ls", "ls")
        
        # Verify the command was wrapped
        called_cmd = mock_subproc.call_args[0][0]
        assert "chroot /host" in called_cmd
        assert "cd /app" in called_cmd
