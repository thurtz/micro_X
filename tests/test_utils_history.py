# tests/test_utils_history.py

import pytest
from unittest.mock import mock_open, patch, MagicMock
from utils import history

@patch("builtins.print")
def test_display_history_file_not_found(mock_print):
    with patch("builtins.open", side_effect=FileNotFoundError):
        history.display_history("non_existent_file")
        mock_print.assert_called_with("Error: History file not found at non_existent_file")

@patch("builtins.print")
def test_display_history_success(mock_print):
    mock_content = "+cmd1\n+cmd2\n-ignored\n+cmd3\n"
    with patch("builtins.open", mock_open(read_data=mock_content)):
        history.display_history("dummy_path", num_lines=100)
        
        # Should verify printed calls.
        # Enumerate starts at 1.
        # Filtered commands: cmd1, cmd2, cmd3
        expected_calls = [
            ("    1  cmd1",),
            ("    2  cmd2",),
            ("    3  cmd3",)
        ]
        # Check that print was called with these strings (ignoring exact formatting potentially, but let's try exact)
        # mock_print.call_args_list contains call objects.
        # call[0] is args tuple.
        
        calls = [c[0] for c in mock_print.call_args_list]
        assert calls == expected_calls

@patch("builtins.print")
def test_display_history_limit(mock_print):
    mock_content = "+cmd1\n+cmd2\n+cmd3\n"
    with patch("builtins.open", mock_open(read_data=mock_content)):
        history.display_history("dummy_path", num_lines=2)
        
        # Should show last 2: cmd2 (index 2), cmd3 (index 3)
        expected_calls = [
            ("    2  cmd2",),
            ("    3  cmd3",)
        ]
        calls = [c[0] for c in mock_print.call_args_list]
        assert calls == expected_calls

@patch("builtins.print")
def test_display_history_all(mock_print):
    mock_content = "+cmd1\n+cmd2\n"
    with patch("builtins.open", mock_open(read_data=mock_content)):
        # Passing show_all=True overrides limit
        history.display_history("dummy_path", num_lines=1, show_all=True)
        
        expected_calls = [
            ("    1  cmd1",),
            ("    2  cmd2",)
        ]
        calls = [c[0] for c in mock_print.call_args_list]
        assert calls == expected_calls

@patch("builtins.print")
def test_display_history_empty(mock_print):
    with patch("builtins.open", mock_open(read_data="")):
        history.display_history("dummy_path")
        mock_print.assert_not_called()
