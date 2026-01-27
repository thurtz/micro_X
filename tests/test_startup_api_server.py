# tests/test_startup_api_server.py

import pytest
import asyncio
import json
import os
from unittest.mock import MagicMock, AsyncMock, patch
from modules.startup import api_server

@pytest.fixture
def mock_lock():
    lock = MagicMock() # Base as MagicMock for sync attributes
    lock.acquire = AsyncMock() # Async method
    lock.release = MagicMock() # Sync method
    lock.locked = MagicMock(return_value=True) # Sync method
    return lock

@pytest.fixture
def mock_shell_engine():
    engine = MagicMock()
    engine.get_user_input_from_api = AsyncMock(return_value="User Input")
    return engine

@pytest.mark.asyncio
async def test_api_server_handler_get_input_success(mock_lock, mock_shell_engine):
    reader = AsyncMock()
    reader.read.return_value = json.dumps({"type": "get_input", "prompt": "Name?"}).encode()
    
    writer = MagicMock()
    writer.get_extra_info.return_value = "addr"
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    
    await api_server.api_server_handler(reader, writer, mock_lock, mock_shell_engine)
    
    # Check that shell engine was called
    mock_shell_engine.get_user_input_from_api.assert_called_with("Name?")
    
    # Check response
    writer.write.assert_called()
    args = writer.write.call_args[0][0]
    response = json.loads(args.decode())
    assert response["status"] == "ok"
    assert response["value"] == "User Input"

@pytest.mark.asyncio
async def test_api_server_handler_invalid_json(mock_lock, mock_shell_engine):
    reader = AsyncMock()
    reader.read.return_value = b"{invalid_json"
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    
    await api_server.api_server_handler(reader, writer, mock_lock, mock_shell_engine)
    
    args = writer.write.call_args[0][0]
    response = json.loads(args.decode())
    assert response["status"] == "error"
    assert "Invalid JSON" in response["error"]

@pytest.mark.asyncio
async def test_api_server_handler_no_shell_engine(mock_lock):
    reader = AsyncMock()
    reader.read.return_value = json.dumps({"type": "get_input"}).encode()
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    
    await api_server.api_server_handler(reader, writer, mock_lock, None)
    
    args = writer.write.call_args[0][0]
    response = json.loads(args.decode())
    assert response["status"] == "error"
    assert "Shell engine not initialized" in response["error"]

@patch("asyncio.start_unix_server", new_callable=AsyncMock)
@patch("os.remove")
@patch("os.path.exists", return_value=True)
@pytest.mark.asyncio
async def test_start_api_server(mock_exists, mock_remove, mock_start_server):
    mock_server_obj = AsyncMock()
    mock_server_obj.sockets = [MagicMock()]
    mock_server_obj.serve_forever = AsyncMock()
    mock_start_server.return_value = mock_server_obj
    
    input_lock = AsyncMock()
    shell_provider = MagicMock()
    
    # We run start_api_server. It's an async function that runs forever normally.
    # We mock serve_forever to return immediately.
    
    await api_server.start_api_server(input_lock, shell_provider)
    
    mock_remove.assert_called_with(api_server.API_SOCKET_PATH)
    mock_start_server.assert_called_once()
    assert os.environ["MICROX_API_SOCKET"] == api_server.API_SOCKET_PATH
