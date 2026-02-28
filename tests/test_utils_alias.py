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

@patch("builtins.print")
def test_handle_add_alias_empty_command(mock_print):
    args = MagicMock()
    args.add = ["/alias"] # No command
    
    alias.handle_add_alias(args, "dummy_path")
    
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("command for the alias cannot be empty" in c for c in calls)

@patch("builtins.print")
def test_handle_remove_alias_invalid_name(mock_print):
    args = MagicMock()
    args.remove = "no-slash"
    
    alias.handle_remove_alias(args, "dummy_path")
    
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("Alias name must begin with a forward slash" in c for c in calls)

@patch("builtins.print")
@patch("sys.exit")
def test_main_no_args(mock_exit, mock_print):
    with patch("sys.argv", ["alias.py"]):
        alias.main()
    # Should print HELP_TEXT and exit(0)
    mock_print.assert_called_with(alias.HELP_TEXT)
    mock_exit.assert_called_once_with(0)

@patch("builtins.print")
def test_main_help_flag(mock_print):
    # Testing the custom HelpAction
    with patch("sys.argv", ["alias.py", "--help"]):
        # argparse.exit() is called by HelpAction, which usually raises SystemExit
        with pytest.raises(SystemExit):
             alias.main()
    
    # HelpAction prints HELP_TEXT
    mock_print.assert_any_call(alias.HELP_TEXT)

@patch("builtins.print")
@patch("utils.alias.handle_add_alias")
@patch("utils.alias.get_project_root")
def test_main_add_flow(mock_root, mock_handle_add, mock_print):
    mock_root.return_value = "/root"
    with patch("sys.argv", ["alias.py", "--add", "/my", "cmd"]):
        with patch("os.path.join", side_effect=lambda *args: "/".join(args)):
             alias.main()
    
    mock_handle_add.assert_called_once()
    # Check that it called with the expected user_aliases_path
    assert mock_handle_add.call_args[0][1] == "/root/config/user_aliases.json"

@patch("builtins.print")
@patch("utils.alias.handle_remove_alias")
@patch("utils.alias.get_project_root")
def test_main_remove_flow(mock_root, mock_handle_remove, mock_print):
    mock_root.return_value = "/root"
    with patch("sys.argv", ["alias.py", "--remove", "/my"]):
        with patch("os.path.join", side_effect=lambda *args: "/".join(args)):
             alias.main()
    mock_handle_remove.assert_called_once()

@patch("builtins.print")
@patch("utils.alias.handle_list_aliases")
@patch("utils.alias.get_project_root")
def test_main_list_flow(mock_root, mock_handle_list, mock_print):
    mock_root.return_value = "/root"
    with patch("sys.argv", ["alias.py", "--list"]):
        with patch("os.path.join", side_effect=lambda *args: "/".join(args)):
             alias.main()
    mock_handle_list.assert_called_once()
