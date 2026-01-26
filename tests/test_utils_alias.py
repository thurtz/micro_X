# tests/test_utils_alias.py

import pytest
from unittest.mock import MagicMock, patch
import sys
from utils import alias

@patch("builtins.print")
@patch("utils.alias.save_json_file")
@patch("utils.alias.load_json_file")
def test_handle_add_alias_success(mock_load, mock_save, mock_print):
    args = MagicMock()
    args.add = ["/myalias", "ls", "-l"]
    
    mock_load.return_value = {}
    mock_save.return_value = True
    
    alias.handle_add_alias(args, "dummy_path")
    
    # Check that it saved the correct dict
    mock_save.assert_called_once_with("dummy_path", {"/myalias": "ls -l"})
    # Check success message
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("successfully mapped" in c for c in calls)

@patch("builtins.print")
def test_handle_add_alias_invalid_name(mock_print):
    args = MagicMock()
    args.add = ["myalias", "ls"] # Missing slash
    
    alias.handle_add_alias(args, "dummy_path")
    
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("Alias name must begin with a forward slash" in c for c in calls)

@patch("builtins.print")
def test_handle_add_alias_reserved(mock_print):
    args = MagicMock()
    args.add = ["/help", "echo"]
    
    # Mock the constant in the module
    with patch("utils.alias.RESERVED_COMMAND_NAMES", ["/help"]):
        alias.handle_add_alias(args, "dummy_path")
        
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("reserved command" in c for c in calls)

@patch("builtins.print")
@patch("utils.alias.save_json_file")
@patch("utils.alias.load_json_file")
def test_handle_remove_alias_success(mock_load, mock_save, mock_print):
    args = MagicMock()
    args.remove = "/myalias"
    
    mock_load.return_value = {"/myalias": "ls"}
    mock_save.return_value = True
    
    alias.handle_remove_alias(args, "dummy_path")
    
    mock_save.assert_called_once_with("dummy_path", {})
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("successfully removed" in c for c in calls)

@patch("builtins.print")
@patch("utils.alias.load_json_file")
def test_handle_remove_alias_not_found(mock_load, mock_print):
    args = MagicMock()
    args.remove = "/unknown"
    
    mock_load.return_value = {"/other": "ls"}
    
    alias.handle_remove_alias(args, "dummy_path")
    
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("not found" in c for c in calls)

@patch("builtins.print")
@patch("utils.alias.load_json_file")
@patch("utils.alias.format_aliases_list")
def test_handle_list_aliases(mock_format, mock_load, mock_print):
    # side_effect for multiple calls: first default, then user
    mock_load.side_effect = [{"/default": "cmd"}, {"/user": "cmd"}]
    mock_format.return_value = "Formatted List"
    
    alias.handle_list_aliases("def_path", "user_path")
    
    mock_format.assert_called_once()
    mock_print.assert_called_once_with("Formatted List")
