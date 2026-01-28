# tests/test_native_shell_processor.py

import pytest
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch
from modules.native_shell_processor import NativeShellProcessor

@pytest.fixture
def mock_deps():
    return {
        "config": {},
        "ai_handler": MagicMock(),
        "ollama_manager": MagicMock(),
        "embedding_manager": MagicMock()
    }

@pytest.fixture
def processor(mock_deps):
    return NativeShellProcessor(
        mock_deps["config"],
        mock_deps["ai_handler"],
        mock_deps["ollama_manager"],
        mock_deps["embedding_manager"]
    )

@pytest.mark.asyncio
async def test_handle_ai_confirmation_yes(processor):
    mock_stdin = AsyncMock()
    # User types 'y'
    mock_stdin.read.return_value = b'y'
    
    with patch("sys.stdout.buffer.write") as mock_write, \
         patch("sys.stdout.flush"):
        res = await processor._handle_ai_confirmation("ls -l", "ls", mock_stdin, 1)
        assert res == "ls -l"
        # Verify prompt was written to stdout
        written_data = b"".join(call[0][0] for call in mock_write.call_args_list)
        assert b"Execute?" in written_data
        assert b"Yes" in written_data

@pytest.mark.asyncio
async def test_handle_ai_confirmation_no(processor):
    mock_stdin = AsyncMock()
    # User types 'n'
    mock_stdin.read.return_value = b'n'
    
    with patch("sys.stdout.buffer.write"), \
         patch("sys.stdout.flush"):
        res = await processor._handle_ai_confirmation("ls -l", "ls", mock_stdin, 1)
        assert res == "ls" # Returns original command

@pytest.mark.asyncio
async def test_process_intercepted_command_exit(processor):
    mock_stdin = AsyncMock()
    with patch("os.write") as mock_write:
        await processor._process_intercepted_command("exit", 1, mock_stdin)
        mock_write.assert_called_once_with(1, b"exit\n")

@pytest.mark.asyncio
async def test_handle_ai_confirmation_modify(processor):
    mock_stdin = AsyncMock()
    mock_stdin.read.return_value = b'm'
    
    with patch("sys.stdout.buffer.write"), \
         patch("sys.stdout.flush"):
        res = await processor._handle_ai_confirmation("ls -l", "ls", mock_stdin, 1)
        assert res is None

@pytest.mark.asyncio
async def test_handle_ai_confirmation_explain(processor, mock_deps):
    mock_stdin = AsyncMock()
    # First 'e', then 'y'
    mock_stdin.read.side_effect = [b'e', b'y']
    
    mock_deps["ai_handler"].explain_linux_command_with_ai = AsyncMock(return_value="It lists files.")
    
    with patch("sys.stdout.buffer.write") as mock_write, \
         patch("sys.stdout.flush"):
        res = await processor._handle_ai_confirmation("ls -l", "ls", mock_stdin, 1)
        
        mock_deps["ai_handler"].explain_linux_command_with_ai.assert_called_once()
        assert res == "ls -l"
        
        # Check if explanation was written
        written_data = b"".join(call[0][0] for call in mock_write.call_args_list)
        assert b"--- AI Explanation ---" in written_data
        assert b"It lists files." in written_data

@pytest.mark.asyncio
async def test_process_intercepted_command_ai_down(processor, mock_deps):
    mock_deps["ollama_manager"].is_ollama_server_running = AsyncMock(return_value=False)
    
    with patch("os.write") as mock_write:
        await processor._process_intercepted_command("cmd", 1, AsyncMock())
        mock_write.assert_called_once_with(1, b"cmd\n")

@pytest.mark.asyncio
async def test_process_intercepted_command_no_suggestion(processor, mock_deps):
    mock_deps["ollama_manager"].is_ollama_server_running = AsyncMock(return_value=True)
    # AI returns same command or None
    mock_deps["ai_handler"].get_validated_ai_command = AsyncMock(return_value=("cmd", "raw"))
    
    with patch("os.write") as mock_write:
        await processor._process_intercepted_command("cmd", 1, AsyncMock())
        # Should execute original since no change
        mock_write.assert_called_once_with(1, b"cmd\n")

@pytest.mark.asyncio
async def test_process_intercepted_command_modify_flow(processor, mock_deps):
    mock_deps["ollama_manager"].is_ollama_server_running = AsyncMock(return_value=True)
    mock_deps["ai_handler"].get_validated_ai_command = AsyncMock(return_value=("ls -l", "raw"))
    
    # Mock confirmation to return None (Modify)
    with patch.object(processor, '_handle_ai_confirmation', return_value=None) as mock_confirm, \
         patch("os.write") as mock_write:
        
        await processor._process_intercepted_command("list files", 1, AsyncMock())
        
        mock_confirm.assert_awaited_once()
        # Should just write newline to reset prompt, not execute anything
        mock_write.assert_called_once_with(1, b'\n')
