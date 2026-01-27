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
async def test_process_intercepted_command_ai_suggests(processor, mock_deps):
    mock_stdin = AsyncMock()
    mock_stdin.read.return_value = b'y' # User confirms AI suggestion
    
    # AI Handler returns a suggestion
    mock_deps["ai_handler"].get_validated_ai_command = AsyncMock(return_value=("ls -l", "raw"))
    # Ollama is running
    mock_deps["ollama_manager"].is_ollama_server_running = AsyncMock(return_value=True)
    
    with patch("os.write") as mock_write, \
         patch("sys.stdout.buffer.write"), \
         patch("sys.stdout.flush"):
        await processor._process_intercepted_command("list files", 1, mock_stdin)
        
        # Should execute the AI suggested command
        mock_write.assert_called_with(1, b"ls -l\n")
