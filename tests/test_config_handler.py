# tests/test_config_handler.py

import pytest
import sys
import os
import json
from unittest.mock import mock_open, patch, MagicMock

# --- Path Setup ---
# This assumes that conftest.py correctly adds the project root to the path.
from modules import config_handler

# --- Test Cases for load_jsonc_file ---

@patch("os.path.exists", return_value=True)
def test_load_jsonc_with_single_line_comments(mock_exists):
    """Tests loading a JSONC file with // style comments."""
    jsonc_content = """
    {
        // This is a key for the user
        "user": "test_user", // Another comment
        "port": 8080,
        "path": "/usr/local" // Final comment
    }
    """
    expected_dict = {"user": "test_user", "port": 8080, "path": "/usr/local"}
    
    with patch("builtins.open", mock_open(read_data=jsonc_content)) as mock_file:
        result = config_handler.load_jsonc_file("dummy/path.jsonc")
        mock_file.assert_called_once_with("dummy/path.jsonc", 'r', encoding='utf-8')
        assert result == expected_dict

@patch("os.path.exists", return_value=True)
def test_load_jsonc_with_multi_line_comments(mock_exists):
    """Tests loading a JSONC file with /* */ style comments."""
    jsonc_content = """
    {
        /* * Main configuration block for the application
         */
        "host": "localhost",
        "enabled": true /* Enable by default */
    }
    """
    expected_dict = {"host": "localhost", "enabled": True}
    
    with patch("builtins.open", mock_open(read_data=jsonc_content)):
        result = config_handler.load_jsonc_file("dummy/path.jsonc")
        assert result == expected_dict

@patch("os.path.exists", return_value=True)
def test_load_jsonc_without_comments(mock_exists):
    """Tests loading a standard JSON file with no comments."""
    json_content = '{"key": "value", "number": 123}'
    expected_dict = {"key": "value", "number": 123}
    
    with patch("builtins.open", mock_open(read_data=json_content)):
        result = config_handler.load_jsonc_file("dummy/path.json")
        assert result == expected_dict

@patch("os.path.exists", return_value=True)
def test_load_jsonc_with_malformed_json(mock_exists):
    """Tests loading a file with a JSON syntax error."""
    malformed_content = '{"key": "value",}' # Trailing comma
    
    with patch("builtins.open", mock_open(read_data=malformed_content)):
        result = config_handler.load_jsonc_file("dummy/path.jsonc")
        assert result is None

@patch("os.path.exists", return_value=False)
def test_load_jsonc_file_not_found(mock_exists):
    """Tests loading a file that does not exist."""
    result = config_handler.load_jsonc_file("non/existent/path.jsonc")
    assert result is None

# --- Test Cases for save_json_file ---

@patch("os.makedirs")
def test_save_json_file_success(mock_makedirs):
    """
    Tests successfully saving data to a JSON file.
    
    FIX: This test is corrected to handle the fact that json.dump with an indent
    makes multiple calls to the file handle's write() method. Instead of asserting
    a single call, we reconstruct the full written content from all calls and
    compare it to the expected formatted string.
    """
    data_to_save = {"user": "test", "settings": {"theme": "dark"}}
    # The expected string must match json.dump's output exactly, including sorting keys.
    expected_json_string = json.dumps(data_to_save, indent=2, sort_keys=True)
    
    m = mock_open()
    with patch("builtins.open", m):
        success = config_handler.save_json_file("dummy/output.json", data_to_save)
        
    assert success is True
    mock_makedirs.assert_called_once_with(os.path.dirname("dummy/output.json"), exist_ok=True)
    m.assert_called_once_with("dummy/output.json", 'w', encoding='utf-8')
    
    # Get the mock file handle
    handle = m()
    
    # Reconstruct the full string written to the file from all the `write` calls
    written_content = "".join(call.args[0] for call in handle.write.call_args_list)
    
    # Assert that the reconstructed content matches the expected formatted JSON
    assert written_content == expected_json_string


@patch("os.makedirs")
def test_save_json_file_io_error(mock_makedirs):
    """Tests handling of an IOError during file save."""
    data_to_save = {"key": "value"}
    
    m = mock_open()
    m.side_effect = IOError("Permission denied")
    
    with patch("builtins.open", m):
        success = config_handler.save_json_file("dummy/protected.json", data_to_save)
        
    assert success is False

@patch("os.makedirs")
def test_save_json_file_type_error(mock_makedirs):
    """Tests handling of non-serializable data."""
    # A set is not JSON serializable
    data_to_save = {"unserializable": {1, 2, 3}}
    
    m = mock_open()
    with patch("builtins.open", m):
        success = config_handler.save_json_file("dummy/output.json", data_to_save)
        
    assert success is False
