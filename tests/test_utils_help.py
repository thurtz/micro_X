# tests/test_utils_help.py

import pytest
from unittest.mock import MagicMock, patch
from utils import help as help_util

@pytest.fixture
def mock_argparse(mocker):
    mock_parser = MagicMock()
    mocker.patch("argparse.ArgumentParser", return_value=mock_parser)
    return mock_parser

@patch("builtins.print")
def test_main_general_help(mock_print, mock_argparse):
    mock_argparse.parse_known_args.return_value = (MagicMock(topic='general'), [])
    help_util.main()
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("micro_X AI-Enhanced Shell" in c for c in calls)

@patch("builtins.print")
def test_main_translate_help(mock_print, mock_argparse):
    mock_argparse.parse_known_args.return_value = (MagicMock(topic='translate'), [])
    help_util.main()
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("AI Translation Features" in c for c in calls)

@patch("builtins.print")
@patch("utils.help.get_help_text_from_module")
def test_main_module_help(mock_get_help, mock_print, mock_argparse):
    mock_argparse.parse_known_args.return_value = (MagicMock(topic='alias'), [])
    mock_get_help.return_value = "Alias Help"
    
    help_util.main()
    
    mock_get_help.assert_called_once()
    mock_print.assert_called_with("Alias Help")

@patch("builtins.print")
def test_main_unknown_topic(mock_print, mock_argparse):
    mock_argparse.parse_known_args.return_value = (MagicMock(topic='unknown'), [])
    
    with pytest.raises(SystemExit) as e:
        help_util.main()
    assert e.value.code == 1
    
    calls = [c[0][0] for c in mock_print.call_args_list]
    assert any("Unknown help topic" in c for c in calls)
