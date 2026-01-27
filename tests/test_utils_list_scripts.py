# tests/test_utils_list_scripts.py

import pytest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os
from utils import list_scripts

@patch("os.listdir")
@patch("os.path.isdir")
@patch("os.path.isfile")
def test_get_scripts_from_directory_success(mock_isfile, mock_isdir, mock_listdir):
    mock_isdir.return_value = True
    mock_listdir.return_value = ["script1.py", "script2.py", "not_a_script.txt", "__init__.py"]
    mock_isfile.return_value = True
    
    scripts = list_scripts.get_scripts_from_directory("/dummy/path")
    
    assert scripts == ["script1", "script2"]

@patch("os.path.isdir", return_value=False)
def test_get_scripts_from_directory_not_dir(mock_isdir):
    scripts = list_scripts.get_scripts_from_directory("/dummy/path")
    assert scripts == []

@patch("os.listdir", side_effect=OSError("Read error"))
@patch("os.path.isdir", return_value=True)
def test_get_scripts_from_directory_oserror(mock_isdir, mock_listdir):
    scripts = list_scripts.get_scripts_from_directory("/dummy/path")
    assert scripts == []

@patch("builtins.print")
@patch("utils.list_scripts.get_scripts_from_directory")
@patch("utils.list_scripts.load_json_file")
@patch("utils.list_scripts.get_project_root", return_value="/root")
def test_main_list_all(mock_root, mock_load_json, mock_get_scripts, mock_print):
    # Mock return values
    mock_get_scripts.side_effect = [["util1"], ["script1"]] # utils then user scripts
    mock_load_json.return_value = {} # aliases
    
    # Mock args
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_parse.return_value.type = 'all'
        mock_parse.return_value.name = None
        
        list_scripts.main()
        
        # Verify calls
        calls = [c[0][0] for c in mock_print.call_args_list]
        assert any("Built-in Utilities" in str(c) for c in calls)
        assert any("User Scripts" in str(c) for c in calls)
        assert any("- util1" in str(c) for c in calls)
        assert any("- script1" in str(c) for c in calls)

@patch("builtins.print")
@patch("utils.list_scripts.get_scripts_from_directory")
@patch("utils.list_scripts.load_json_file")
@patch("utils.list_scripts.get_project_root", return_value="/root")
def test_main_filter_name(mock_root, mock_load_json, mock_get_scripts, mock_print):
    mock_get_scripts.side_effect = [["git_util", "other_util"], ["git_script"]]
    mock_load_json.return_value = {}
    
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_parse.return_value.type = 'all'
        mock_parse.return_value.name = 'git'
        
        list_scripts.main()
        
        calls = [c[0][0] for c in mock_print.call_args_list]
        assert any("- git_util" in str(c) for c in calls)
        assert not any("- other_util" in str(c) for c in calls)
        assert any("- git_script" in str(c) for c in calls)
