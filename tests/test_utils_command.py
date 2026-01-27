# tests/test_utils_command.py

import pytest
from unittest.mock import MagicMock, patch
import sys
from utils import command

@patch("modules.category_manager.init_category_manager")
@patch("builtins.print")
def test_main_no_args(mock_print, mock_init):
    # No args -> Help
    with patch("sys.argv", ["command.py"]):
        with pytest.raises(SystemExit) as e:
            command.main()
        assert e.value.code == 0
    mock_init.assert_called_once()
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("micro_X Help" in c for c in calls)

@patch("modules.category_manager.init_category_manager")
@patch("modules.category_manager.add_command_to_category")
def test_main_add(mock_add, mock_init):
    with patch("sys.argv", ["command.py", "--add", "ls", "simple"]):
        command.main()
    mock_add.assert_called_once_with("ls", "simple")

@patch("modules.category_manager.init_category_manager")
@patch("modules.category_manager.remove_command_from_category")
def test_main_remove(mock_remove, mock_init):
    with patch("sys.argv", ["command.py", "--remove", "ls"]):
        command.main()
    mock_remove.assert_called_once_with("ls")

@patch("modules.category_manager.init_category_manager")
@patch("modules.category_manager.move_command_category")
def test_main_move(mock_move, mock_init):
    with patch("sys.argv", ["command.py", "--move", "ls", "interactive_tui"]):
        command.main()
    mock_move.assert_called_once_with("ls", "interactive_tui")

@patch("modules.category_manager.init_category_manager")
@patch("modules.category_manager.list_categorized_commands")
def test_main_list(mock_list, mock_init):
    with patch("sys.argv", ["command.py", "--list"]):
        command.main()
    mock_list.assert_called_once()

@patch("modules.category_manager.init_category_manager")
@patch("builtins.print")
def test_main_exception(mock_print, mock_init):
    # Simulate exception
    mock_init.side_effect = Exception("Init error")
    with patch("sys.argv", ["command.py", "--list"]):
        with pytest.raises(SystemExit) as e:
            command.main()
        assert e.value.code == 1
    
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("Error initializing category manager" in c for c in calls)
