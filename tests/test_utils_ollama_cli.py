# tests/test_utils_ollama_cli.py

import pytest
import sys
from unittest.mock import MagicMock, patch, AsyncMock
from utils import ollama_cli

@pytest.fixture
def mock_main_module(mocker):
    # Mock the 'main' module to provide 'config' without running main.py logic
    mock_main = MagicMock()
    mock_main.config = {"ollama_service": {}}
    mocker.patch.dict("sys.modules", {"main": mock_main})
    return mock_main

@pytest.mark.asyncio
async def test_main_start(mock_main_module):
    with (
        patch("sys.argv", ["ollama_cli.py", "start"]),
        patch("modules.ollama_manager.explicit_start_ollama_service", new_callable=AsyncMock) as mock_start
    ):
        await ollama_cli.main()
        mock_start.assert_awaited_once()

@pytest.mark.asyncio
async def test_main_stop(mock_main_module):
    with (
        patch("sys.argv", ["ollama_cli.py", "stop"]),
        patch("modules.ollama_manager.explicit_stop_ollama_service", new_callable=AsyncMock) as mock_stop
    ):
        await ollama_cli.main()
        mock_stop.assert_awaited_once()

@pytest.mark.asyncio
async def test_main_status(mock_main_module):
    with (
        patch("sys.argv", ["ollama_cli.py", "status"]),
        patch("modules.ollama_manager.get_ollama_status_info", new_callable=AsyncMock) as mock_status
    ):
        await ollama_cli.main()
        mock_status.assert_awaited_once()

@patch("builtins.print")
@pytest.mark.asyncio
async def test_main_help(mock_print, mock_main_module):
    with patch("sys.argv", ["ollama_cli.py", "help"]):
        await ollama_cli.main()
        calls = [c[0][0] for c in mock_print.call_args_list]
        assert any("micro_X Help: /ollama Utility" in str(c) for c in calls)

def test_print_for_manager(capsys):
    ollama_cli.print_for_manager("Test error", "error")
    captured = capsys.readouterr()
    assert "❌ Error: Test error" in captured.out

    ollama_cli.print_for_manager("Test success", "success")
    captured = capsys.readouterr()
    assert "✅ Success: Test success" in captured.out
