# tests/test_category_manager.py
#
# Unit tests for functions in modules/category_manager.py

import pytest
import json
import os
import logging
from unittest.mock import mock_open, patch, MagicMock

from modules import category_manager
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
        # Access the global variable on the module, not cls
        category_manager._CURRENTLY_LOADED_CATEGORIES = {"simple": ["test_cmd"]}
    # Mock the function on the module
    monkeypatch.setattr(category_manager, 'load_and_merge_command_categories', lambda: mock_load_and_set(None))
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
    
    # Ensure CATEGORY_MAP is populated for the test (just in case)
    if not category_manager.CATEGORY_MAP:
         category_manager.CATEGORY_MAP = {
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

    # This calls the real config_handler.load_jsonc_file, which uses os.path.exists
    # We rely on config_handler using the mocked os.path.exists if possible, 
    # but here we are mocking it at the import source in config_handler?
    # No, we patched it where it is used. config_handler imports os.
    # The patch "modules.config_handler.os.path.exists" patches it in that module.
    
    result = category_manager._load_single_category_file("dummy/non_existent.json")
    
    for cat_name in set(category_manager.CATEGORY_MAP.values()):
        assert cat_name in result and result[cat_name] == []
    
    assert "Configuration file not found at: dummy/non_existent.json" in caplog.text


@patch("modules.config_handler.load_jsonc_file")
def test_load_single_category_file_invalid_json(mock_load_jsonc, caplog):
    """Test loading a file with invalid JSON content."""
    caplog.set_level(logging.ERROR)
    mock_load_jsonc.return_value = None 
    
    if not category_manager.CATEGORY_MAP:
         category_manager.CATEGORY_MAP = {"simple": "simple"}

    result = category_manager._load_single_category_file("dummy/invalid.json")
    
    for cat_name in set(category_manager.CATEGORY_MAP.values()):
        assert cat_name in result and result[cat_name] == []


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
            "simple": "simple", "semi_interactive": "semi_interactive", "interactive_tui": "interactive_tui",
        }

    result = category_manager._load_single_category_file("dummy/structured_error.json")
    
    assert result["simple"] == []
    assert result["semi_interactive"] == ["cmd_semi"]
    assert "interactive_tui" in result and result["interactive_tui"] == []
    assert "Category 'simple' in dummy/structured_error.json is not a list. Resetting to empty list." in caplog.text


# --- Tests for Add/Remove/Modify ---

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
            "simple": "simple", "semi_interactive": "semi_interactive", "interactive_tui": "interactive_tui"
        }

    category_manager.add_command_to_category("new_cmd", "simple")
    
    saved_data = mock_save_user_cats.call_args[0][0]
    assert "new_cmd" in saved_data["simple"]
    mock_load_merge.assert_called_once()
    
    mock_append_output.assert_any_call("✅ Command 'new_cmd' now set as 'simple'.", style_class='success')


@patch("modules.category_manager._load_single_category_file")
@patch("modules.category_manager._save_user_command_categories")
@patch("modules.category_manager.load_and_merge_command_categories")
def test_remove_command_from_category_success(
    mock_load_merge, mock_save_user_cats, mock_load_single, monkeypatch
):
    mock_load_single.return_value = {
        "simple": ["cmd_to_remove"], "semi_interactive": [], "interactive_tui": []
    }
    mock_append_output = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append_output)
    
    category_manager.remove_command_from_category("cmd_to_remove")
    
    saved_data = mock_save_user_cats.call_args[0][0]
    assert "cmd_to_remove" not in saved_data["simple"]
    mock_load_merge.assert_called_once()
    mock_append_output.assert_any_call("🗑️ Command 'cmd_to_remove' removed from your user settings.", style_class='info')


@patch("modules.category_manager._load_single_category_file")
@patch("modules.category_manager._save_user_command_categories")
def test_remove_command_from_category_not_found(
    mock_save_user_cats, mock_load_single, monkeypatch
):
    mock_load_single.return_value = {
        "simple": [], "semi_interactive": [], "interactive_tui": []
    }
    mock_append_output = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append_output)
    
    category_manager.remove_command_from_category("non_existent_cmd")
    
    mock_save_user_cats.assert_not_called()
    mock_append_output.assert_any_call("⚠️ Command 'non_existent_cmd' not found in your user settings.", style_class='warning')


# --- Tests for Subsystem Input Handling ---

def test_handle_command_subsystem_input_add(monkeypatch):
    mock_add = MagicMock()
    monkeypatch.setattr(category_manager, 'add_command_to_category', mock_add)
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
    category_manager.handle_command_subsystem_input('/command add "ls -la" simple')
    mock_add.assert_called_once_with("ls -la", "simple")

def test_handle_command_subsystem_input_remove(monkeypatch):
    mock_remove = MagicMock()
    monkeypatch.setattr(category_manager, 'remove_command_from_category', mock_remove)
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
    category_manager.handle_command_subsystem_input('/command remove "ls -la"')
    mock_remove.assert_called_once_with("ls -la")

def test_handle_command_subsystem_input_run(monkeypatch):
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
    if not category_manager.CATEGORY_MAP:
         category_manager.CATEGORY_MAP = {"simple": "simple", "interactive_tui": "interactive_tui"}
         
    # Valid run
    result = category_manager.handle_command_subsystem_input('/command run simple "echo hi"')
    assert result == {'action': 'force_run', 'command': 'echo hi', 'category': 'simple'}
    
    # Invalid category
    result_invalid = category_manager.handle_command_subsystem_input('/command run invalid_cat "echo hi"')
    assert result_invalid is None
    mock_append.assert_any_call("❌ Invalid category for 'run': 'invalid_cat'.", style_class='error')

def test_handle_command_subsystem_input_list(monkeypatch):
    mock_list = MagicMock()
    monkeypatch.setattr(category_manager, 'list_categorized_commands', mock_list)
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
    category_manager.handle_command_subsystem_input('/command list')
    mock_list.assert_called_once()

def test_handle_command_subsystem_input_help(monkeypatch):
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
    category_manager.handle_command_subsystem_input('/command help')
    mock_append.assert_called()
    assert "add" in mock_append.call_args[0][0] # Check for help text content

def test_handle_command_subsystem_input_unknown_subcommand(monkeypatch):
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
    category_manager.handle_command_subsystem_input('/command unknown_thing')
    mock_append.assert_called()
    assert "Unknown /command subcommand" in mock_append.call_args[0][0]

def test_handle_command_subsystem_input_invalid_structure(monkeypatch):
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
    # Just "/command" with no args
    category_manager.handle_command_subsystem_input('/command')
    mock_append.assert_called()
    assert "Invalid /command structure" in mock_append.call_args[0][0]

# --- Tests for Listing ---

def test_list_categorized_commands(monkeypatch):
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    monkeypatch.setattr(category_manager, '_CURRENTLY_LOADED_CATEGORIES', MOCK_CATEGORIES_DATA)
    
    category_manager.list_categorized_commands()
    
    # Should call append for header, subheaders, and items
    # Header
    mock_append.assert_any_call("📄 Current command categories (defaults + user overrides):", style_class='info-header')
    # Item from simple
    mock_append.assert_any_call("  - ls", style_class='info-item')
    # Subheader for interactive_tui
    # Note: Description might vary, check basic presence
    assert any("interactive_tui" in str(arg) for call in mock_append.call_args_list for arg in call[0])