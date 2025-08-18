# tests/test_category_manager.py
#
# Unit tests for functions in modules/category_manager.py

import pytest
import json
import os
import logging # Import logging module
from unittest.mock import mock_open, patch, MagicMock

# Assuming category_manager.py is in a 'modules' subdirectory
# and its constants like UNKNOWN_CATEGORY_SENTINEL are accessible.
from modules import category_manager
# --- FIX: Import the config_handler to reference its logger name ---
from modules import config_handler


# Sample category data for testing classify_command
MOCK_CATEGORIES_DATA = {
    "simple": ["ls", "pwd", "echo test"],
    "semi_interactive": ["less file.txt", "git log"],
    "interactive_tui": ["vim", "htop"]
}

# --- Tests for classify_command ---

@pytest.fixture
def mock_loaded_categories(monkeypatch):
    """Fixture to temporarily set _CURRENTLY_LOADED_CATEGORIES."""
    monkeypatch.setattr(category_manager, '_CURRENTLY_LOADED_CATEGORIES', MOCK_CATEGORIES_DATA)

def test_classify_command_simple(mock_loaded_categories):
    assert category_manager.classify_command("ls") == "simple"
    assert category_manager.classify_command("echo test") == "simple"

def test_classify_command_semi_interactive(mock_loaded_categories):
    assert category_manager.classify_command("less file.txt") == "semi_interactive"

def test_classify_command_interactive_tui(mock_loaded_categories):
    assert category_manager.classify_command("vim") == "interactive_tui"

def test_classify_command_unknown(mock_loaded_categories):
    assert category_manager.classify_command("unknown_command") == category_manager.UNKNOWN_CATEGORY_SENTINEL

def test_classify_command_empty_string(mock_loaded_categories):
    assert category_manager.classify_command("") == category_manager.UNKNOWN_CATEGORY_SENTINEL

def test_classify_command_not_loaded(monkeypatch):
    """Test behavior when categories are not loaded (should attempt to load)."""
    monkeypatch.setattr(category_manager, '_CURRENTLY_LOADED_CATEGORIES', {})
    def mock_load_and_set(cls):
        cls._CURRENTLY_LOADED_CATEGORIES = {"simple": ["test_cmd"]}
    monkeypatch.setattr(category_manager, 'load_and_merge_command_categories', lambda: mock_load_and_set(category_manager))
    assert category_manager.classify_command("test_cmd") == "simple"
    assert category_manager.classify_command("another_cmd") == category_manager.UNKNOWN_CATEGORY_SENTINEL


# --- Tests for _load_single_category_file ---

@patch("modules.config_handler.load_jsonc_file")
def test_load_single_category_file_valid(mock_load_jsonc, caplog):
    """Test loading a valid category file."""
    caplog.set_level(logging.INFO)
    valid_data = {
        "simple": ["cmd1", "cmd2"],
        "semi_interactive": ["cmd3"],
        "interactive_tui": []
    }
    mock_load_jsonc.return_value = valid_data
    
    # Ensure CATEGORY_MAP is populated for the test
    if not category_manager.CATEGORY_MAP:
         category_manager.CATEGORY_MAP = {
            "1": "simple", "2": "semi_interactive", "3": "interactive_tui",
            "simple": "simple", "semi_interactive": "semi_interactive", "interactive_tui": "interactive_tui",
        }

    result = category_manager._load_single_category_file("dummy/path.json")
    
    assert result["simple"] == ["cmd1", "cmd2"]
    assert result["semi_interactive"] == ["cmd3"]
    assert "interactive_tui" in result and result["interactive_tui"] == []
    mock_load_jsonc.assert_called_once_with("dummy/path.json")
    assert "Successfully loaded and validated categories from dummy/path.json" in caplog.text


@patch("modules.config_handler.os.path.exists", return_value=False)
def test_load_single_category_file_not_exists(mock_exists, caplog):
    """Test loading a non-existent category file by mocking os.path.exists."""
    caplog.set_level(logging.INFO)
    
    if not category_manager.CATEGORY_MAP:
         category_manager.CATEGORY_MAP = {"simple": "simple", "semi_interactive": "semi_interactive", "interactive_tui": "interactive_tui"}

    # This now calls the real config_handler.load_jsonc_file, which will
    # see os.path.exists as False, log the message, and return None.
    result = category_manager._load_single_category_file("dummy/non_existent.json")
    
    # Verify that the function correctly returns the default empty structure
    for cat_name in set(category_manager.CATEGORY_MAP.values()):
        assert cat_name in result and result[cat_name] == []
    
    # Verify that the log message from config_handler was successfully captured
    assert "Configuration file not found at: dummy/non_existent.json" in caplog.text
    mock_exists.assert_called_once_with("dummy/non_existent.json")


@patch("modules.config_handler.load_jsonc_file")
def test_load_single_category_file_invalid_json(mock_load_jsonc, caplog):
    """Test loading a file with invalid JSON content."""
    caplog.set_level(logging.ERROR)
    mock_load_jsonc.return_value = None # config_handler returns None for parse errors
    
    if not category_manager.CATEGORY_MAP:
         category_manager.CATEGORY_MAP = {"simple": "simple"}

    result = category_manager._load_single_category_file("dummy/invalid.json")
    
    for cat_name in set(category_manager.CATEGORY_MAP.values()):
        assert cat_name in result and result[cat_name] == []
    
    # The actual error log ("Error decoding JSON...") is generated inside config_handler.
    # This test correctly verifies that the function handles the None return value gracefully.
    # No need to assert the specific log text here, as that's a detail of config_handler.


@patch("modules.config_handler.load_jsonc_file")
def test_load_single_category_file_incorrect_structure(mock_load_jsonc, caplog):
    """Test loading a file where a category is not a list."""
    caplog.set_level(logging.WARNING)
    structured_data = {
        "simple": "not-a-list",
        "semi_interactive": ["cmd_semi"],
    }
    mock_load_jsonc.return_value = structured_data
    
    if not category_manager.CATEGORY_MAP:
         category_manager.CATEGORY_MAP = {
            "1": "simple", "2": "semi_interactive", "3": "interactive_tui",
            "simple": "simple", "semi_interactive": "semi_interactive", "interactive_tui": "interactive_tui",
        }

    result = category_manager._load_single_category_file("dummy/structured_error.json")
    
    assert result["simple"] == []
    assert result["semi_interactive"] == ["cmd_semi"]
    assert "interactive_tui" in result and result["interactive_tui"] == []
    assert "Category 'simple' in dummy/structured_error.json is not a list. Resetting to empty list." in caplog.text


@patch("modules.category_manager._load_single_category_file")
@patch("modules.category_manager._save_user_command_categories")
@patch("modules.category_manager.load_and_merge_command_categories")
def test_add_command_to_category_new_command(
    mock_load_merge, mock_save_user_cats, mock_load_single, monkeypatch
):
    mock_load_single.return_value = {
        "simple": [], "semi_interactive": [], "interactive_tui": []
    }
    mock_append_output = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append_output)
    
    if not category_manager.CATEGORY_MAP:
         category_manager.CATEGORY_MAP = {
            "1": "simple", "simple": "simple",
            "2": "semi_interactive", "semi_interactive": "semi_interactive",
            "3": "interactive_tui", "interactive_tui": "interactive_tui"
        }

    category_manager.add_command_to_category("new_cmd", "simple")
    
    saved_data = mock_save_user_cats.call_args[0][0]
    assert "new_cmd" in saved_data["simple"]
    mock_load_merge.assert_called_once()
    
    expected_message = "✅ Command 'new_cmd' now set as 'simple'."
    mock_append_output.assert_any_call(
        expected_message,
        style_class='success'
    )
