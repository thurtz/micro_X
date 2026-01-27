# tests/test_config_handler.py

import pytest
import sys
import os
import json
from unittest.mock import mock_open, patch, MagicMock

from modules import config_handler

# --- Test Cases for load_jsonc_file ---

@patch("os.path.exists", return_value=True)
def test_load_jsonc_with_single_line_comments(mock_exists):
    jsonc_content = """
    {
        // comment
        "user": "test_user",
        "port": 8080
    }
    """
    expected = {"user": "test_user", "port": 8080}
    with patch("builtins.open", mock_open(read_data=jsonc_content)):
        assert config_handler.load_jsonc_file("path.jsonc") == expected

@patch("os.path.exists", return_value=True)
def test_load_jsonc_with_multi_line_comments(mock_exists):
    jsonc_content = """
    {
        /* multi
           line */
        "host": "localhost"
    }
    """
    expected = {"host": "localhost"}
    with patch("builtins.open", mock_open(read_data=jsonc_content)):
        assert config_handler.load_jsonc_file("path.jsonc") == expected

@patch("os.path.exists", return_value=True)
def test_load_jsonc_malformed(mock_exists):
    malformed = '{"key": "value",}' # Trailing comma usually fails standard JSON
    with patch("builtins.open", mock_open(read_data=malformed)):
        assert config_handler.load_jsonc_file("path.jsonc") is None

@patch("os.path.exists", return_value=False)
def test_load_jsonc_not_found(mock_exists):
    assert config_handler.load_jsonc_file("missing.jsonc") is None

@patch("os.path.exists", return_value=True)
def test_load_jsonc_permission_error(mock_exists):
    with patch("builtins.open", side_effect=PermissionError):
        assert config_handler.load_jsonc_file("secret.jsonc") is None

@patch("os.path.exists", return_value=True)
def test_load_jsonc_only_comments(mock_exists):
    content = "// just a comment"
    with patch("builtins.open", mock_open(read_data=content)):
        # json.loads("") fails, so it should return None or handled gracefully
        assert config_handler.load_jsonc_file("empty.jsonc") is None

# --- Test Cases for save_json_file ---

@patch("os.makedirs")
def test_save_json_file_success(mock_makedirs):
    data = {"a": 1, "b": 2}
    expected = json.dumps(data, indent=2, sort_keys=True)
    m = mock_open()
    with patch("builtins.open", m):
        assert config_handler.save_json_file("out.json", data) is True
    
    handle = m()
    written = "".join(call.args[0] for call in handle.write.call_args_list)
    assert written == expected

@patch("os.makedirs")
def test_save_json_file_makedirs_fail(mock_makedirs):
    mock_makedirs.side_effect = OSError("Permission denied")
    assert config_handler.save_json_file("/root/out.json", {"a": 1}) is False

def test_save_json_file_serialization_error():
    # Sets are not serializable
    assert config_handler.save_json_file("out.json", {1, 2, 3}) is False