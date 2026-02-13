# tests/test_native_shell_processor.py

import pytest
import os
import sys
import termios
import tty
import fcntl
from unittest.mock import MagicMock, AsyncMock, patch, call
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

@pytest.mark.asyncio
async def test_process_intercepted_command_execute_suggestion(processor, mock_deps):
    mock_deps["ollama_manager"].is_ollama_server_running = AsyncMock(return_value=True)
    # AI suggests 'ls -la', original was 'ls'
    mock_deps["ai_handler"].get_validated_ai_command = AsyncMock(return_value=("ls -la", "ls"))
    
    # Mock confirmation to return the suggestion (User chose Yes)
    with patch.object(processor, '_handle_ai_confirmation', return_value="ls -la") as mock_confirm, \
         patch("os.write") as mock_write:
        
        await processor._process_intercepted_command("ls", 1, AsyncMock())
        
        mock_confirm.assert_awaited_once()
        # Should execute the suggestion
        mock_write.assert_called_once_with(1, b"ls -la\n")

    @pytest.mark.asyncio
    async def test_run_child_process(processor):
        """Test the child process branch of run()."""
        processor.shell = "/bin/bash"
        with patch("pty.fork", return_value=(0, 123)), \
             patch("os.execve") as mock_execve, \
             patch("os.environ.copy", return_value={"ENV": "VAR"}), \
             patch("shutil.which", return_value="/bin/bash"):
            
            # In child process, run() should not await anything complex or return
            # It calls execve which replaces the process, so in a test we expect it to be called.
            
            await processor.run()
            
            mock_execve.assert_called_once()
            args = mock_execve.call_args
            assert args[0][0] == "/bin/bash" # shell path
            assert args[0][1] == ["/bin/bash"] # argv
            assert args[0][2] == {"ENV": "VAR"} # env

@pytest.mark.asyncio
async def test_run_parent_lifecycle(processor):
    """Test the parent process lifecycle in run()."""
    mock_loop = MagicMock()
    mock_loop.create_task = MagicMock()
    # connect_read_pipe returns a transport, protocol pair. We can ignore them.
    mock_loop.connect_read_pipe = AsyncMock(return_value=(MagicMock(), MagicMock()))
    mock_loop.run_in_executor = AsyncMock()

    with patch("pty.fork", return_value=(1234, 5)), \
         patch("termios.tcgetattr"), \
         patch("termios.tcsetattr"), \
         patch("tty.setraw"), \
         patch("fcntl.ioctl"), \
         patch("shutil.get_terminal_size", return_value=(24, 80)), \
         patch("asyncio.get_running_loop", return_value=mock_loop), \
         patch("os.waitpid"), \
         patch("sys.stdin.fileno", return_value=0), \
         patch("os.fdopen", return_value=MagicMock()), \
         patch("asyncio.StreamReader") as mock_stream_reader_cls:

        # Setup mocked readers to be at EOF immediately so tasks finish
        mock_reader_instance = MagicMock()
        mock_reader_instance.at_eof.side_effect = [False, True] # Run once then stop
        mock_reader_instance.read = AsyncMock(return_value=b'') # Return empty bytes
        mock_stream_reader_cls.return_value = mock_reader_instance

        await processor.run()

        # Close the coroutines that were passed to create_task to avoid warnings
        for call_args in mock_loop.create_task.call_args_list:
            call_args[0][0].close()

        # Check setup
        tty.setraw.assert_called_once_with(0)
        
        # Check resize handler registration
        mock_loop.add_signal_handler.assert_called()
        
        # Check connect_read_pipe called for stdin (pty_to_user is a task, so not run yet)
        assert mock_loop.connect_read_pipe.call_count == 1
        
        # Check tasks created
        assert mock_loop.create_task.call_count == 2
        
        # Check waitpid called
        mock_loop.run_in_executor.assert_called_with(None, os.waitpid, 1234, 0)
        
        # Check cleanup
        mock_loop.remove_signal_handler.assert_called()
        termios.tcsetattr.assert_called_once()

@pytest.mark.asyncio
async def test_run_input_processing(processor):
    """Test that user input is buffered and sent to process_intercepted_command."""
    mock_loop = MagicMock()
    mock_loop.connect_read_pipe = AsyncMock(return_value=(MagicMock(), MagicMock()))
    mock_loop.run_in_executor = AsyncMock()
    # Create a real future for create_task so we can await the tasks if needed, 
    # but here we just need them to not crash.
    mock_loop.create_task = MagicMock()

    # We need to distinguish between stdin_reader (user input) and pty_reader (output).
    # run() creates two StreamReaders.
    # The first one created is stdin_reader. The second is pty_reader (inside pty_to_user).
    
    mock_stdin_reader = MagicMock()
    # Simulate user typing 'l', 's', '\n'
    # .read(1) is called in a loop.
    # Returns: 'l', 's', '\n', then empty bytes to stop the loop?
    # The loop condition is `while not reader.at_eof():`.
    # So we need at_eof to return False for a while, then True.
    
    # Sequence of calls:
    # 1. at_eof? False
    # 2. read(1) -> 'l'
    # 3. at_eof? False
    # 4. read(1) -> 's'
    # 5. at_eof? False
    # 6. read(1) -> '\n'
    # 7. at_eof? True
    
    mock_stdin_reader.at_eof.side_effect = [False, False, False, True]
    mock_stdin_reader.read = AsyncMock(side_effect=[b'l', b's', b'\n', b''])
    
    mock_pty_reader = MagicMock()
    mock_pty_reader.at_eof.return_value = True # No pty output
    
    with patch("pty.fork", return_value=(1234, 5)), \
         patch("termios.tcgetattr"), \
         patch("termios.tcsetattr"), \
         patch("tty.setraw"), \
         patch("fcntl.ioctl"), \
         patch("shutil.get_terminal_size", return_value=(24, 80)), \
         patch("asyncio.get_running_loop", return_value=mock_loop), \
         patch("os.waitpid"), \
         patch("sys.stdin.fileno", return_value=0), \
         patch("os.fdopen", return_value=MagicMock()), \
         patch("asyncio.StreamReader", side_effect=[mock_stdin_reader, mock_pty_reader]), \
         patch("sys.stdout.buffer.write") as mock_stdout_write, \
         patch.object(processor, '_process_intercepted_command') as mock_process:

        # We need to execute the inner async function `user_to_pty`.
        # Since we mocked create_task, the tasks won't actually run automatically.
        # We need to capture the coroutine passed to create_task and await it manually
        # OR just let the real create_task run if we didn't mock the loop so heavily.
        
        # But we mocked `get_running_loop`.
        # Strategy: Run the `processor.run()` but since `create_task` is mocked, 
        # the inner functions won't run.
        # We need to extract them.
        
        # Actually, let's NOT mock create_task?
        # If we use `asyncio.get_running_loop`, we get the REAL loop if we don't mock it.
        # But `run()` calls `loop.connect_read_pipe` which needs a real file descriptor unless mocked.
        
        # Better approach: Capture the coroutine from the `create_task` call arguments.
        
        await processor.run()
        
        # Retrieve the tasks created
        # Expected: 2 calls to create_task.
        # Call 1: user_to_pty(stdin_reader)
        # Call 2: pty_to_user()
        
        assert mock_loop.create_task.call_count == 2
        user_task_coro = mock_loop.create_task.call_args_list[0][0][0]
        
        # Now run the captured coroutine
        await user_task_coro
        
        # Close other coroutines (like pty_to_user)
        for call_args in mock_loop.create_task.call_args_list[1:]:
            call_args[0][0].close()
        
        # Verify echo happened
        # We expect 'l', 's', '\r\n' to be written
        # mock_stdout_write calls: b'l', b's', b'\r\n'
        assert call(b'l') in mock_stdout_write.call_args_list
        assert call(b's') in mock_stdout_write.call_args_list
        assert call(b'\r\n') in mock_stdout_write.call_args_list
        
        # Verify processing triggered
        mock_process.assert_called_once()
        args = mock_process.call_args
        assert args[0][0] == "ls"
