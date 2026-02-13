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

def test_handle_command_subsystem_usage_errors(monkeypatch):
    """Test various usage errors in the subsystem."""
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
    # remove needs 3 parts
    category_manager.handle_command_subsystem_input("/command remove")
    assert "Usage: /command remove" in mock_append.call_args[0][0]
    
    # list needs exactly 2 parts
    category_manager.handle_command_subsystem_input("/command list extra")
    assert "Usage: /command list" in mock_append.call_args[0][0]
    
    # move needs 4 parts
    category_manager.handle_command_subsystem_input("/command move cmd")
    assert "Usage: /command move" in mock_append.call_args[0][0]
    
    # run needs 4 parts
    category_manager.handle_command_subsystem_input("/command run cat")
    assert "Usage: /command run" in mock_append.call_args[0][0]

def test_handle_command_subsystem_input_invalid_structure(monkeypatch):
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
    # Just "/command" with no args
    category_manager.handle_command_subsystem_input('/command')
    mock_append.assert_called()
    assert "Invalid /command structure" in mock_append.call_args[0][0]

# --- Tests for Listing ---

def test_init_category_manager(monkeypatch):
    """Test initialization and path construction."""
    mock_append = MagicMock()
    with patch("modules.category_manager.load_and_merge_command_categories") as mock_load:
        category_manager.init_category_manager("/base", "cfg", mock_append)
        
        assert category_manager._SCRIPT_DIR_PATH == "/base"
        assert category_manager._CONFIG_DIR_NAME_CONST == "cfg"
        assert category_manager._append_output_func_ref == mock_append
        assert category_manager.DEFAULT_CATEGORY_FILE_PATH == "/base/cfg/default_command_categories.json"
        assert category_manager.USER_CATEGORY_FILE_PATH == "/base/cfg/user_command_categories.json"
        mock_load.assert_called_once()

@patch("modules.category_manager._load_single_category_file")
def test_load_and_merge_full_logic(mock_load_single, monkeypatch):
    """Test merging default and user categories with overrides and de-duplication."""
    # Setup paths so it doesn't error
    monkeypatch.setattr(category_manager, 'DEFAULT_CATEGORY_FILE_PATH', '/d')
    monkeypatch.setattr(category_manager, 'USER_CATEGORY_FILE_PATH', '/u')
    
    # Defaults: cmd1 is simple, cmd2 is semi
    default_data = {
        "simple": ["cmd1"],
        "semi_interactive": ["cmd2"],
        "interactive_tui": []
    }
    # User: Move cmd1 to interactive_tui, add cmd3 to simple
    user_data = {
        "simple": ["cmd3"],
        "semi_interactive": [],
        "interactive_tui": ["cmd1"]
    }
    
    mock_load_single.side_effect = [default_data, user_data]
    
    with patch("os.path.exists", return_value=True):
        category_manager.load_and_merge_command_categories()
        
    merged = category_manager._CURRENTLY_LOADED_CATEGORIES
    # cmd1 should be REMOVED from simple and ADDED to interactive_tui
    assert "cmd1" not in merged["simple"]
    assert "cmd1" in merged["interactive_tui"]
    # cmd2 remains in semi
    assert "cmd2" in merged["semi_interactive"]
    # cmd3 added to simple
    assert "cmd3" in merged["simple"]

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

def test_list_categorized_commands_no_callback(monkeypatch, caplog):
    """Test error when callback is missing."""
    monkeypatch.setattr(category_manager, '_append_output_func_ref', None)
    category_manager.list_categorized_commands()
    assert "append_output function not available" in caplog.text

@patch("modules.category_manager.load_and_merge_command_categories")
def test_list_categorized_commands_load_fail(mock_load, monkeypatch):
    """Test error when loading fails during list."""
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    monkeypatch.setattr(category_manager, '_CURRENTLY_LOADED_CATEGORIES', {})
    
    # Simulate load failure by keeping categories empty
    category_manager.list_categorized_commands()
    mock_append.assert_any_call("❌ Error: Categories could not be loaded for listing.", style_class='error')

def test_move_command_category(monkeypatch):
    """Test move is an alias for add."""
    mock_add = MagicMock()
    monkeypatch.setattr(category_manager, 'add_command_to_category', mock_add)
    category_manager.move_command_category("cmd", "2")
    mock_add.assert_called_once_with("cmd", "2")

def test_save_user_categories_no_path(monkeypatch, caplog):
    """Test save error when path is missing."""
    monkeypatch.setattr(category_manager, 'USER_CATEGORY_FILE_PATH', None)
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
    category_manager._save_user_command_categories({})
    assert "User category path not initialized" in caplog.text
    mock_append.assert_called_with("❌ Error: User category path not configured.", style_class='error')

@patch("modules.config_handler.save_json_file", return_value=False)
def test_save_user_categories_fail(mock_save, monkeypatch, caplog):
    """Test behavior when save fails."""
    monkeypatch.setattr(category_manager, 'USER_CATEGORY_FILE_PATH', '/path')
    mock_append = MagicMock()
    monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
    category_manager._save_user_command_categories({})
    assert "Failed to save user categories" in caplog.text
    mock_append.assert_called_with("❌ Error saving user categories.", style_class='error')

@patch("modules.category_manager.load_and_merge_command_categories")
def test_classify_command_load_fail(mock_load, monkeypatch, caplog):
    """Test classify when load fails to populate categories."""
    monkeypatch.setattr(category_manager, '_CURRENTLY_LOADED_CATEGORIES', {})
    res = category_manager.classify_command("cmd")
    assert res == category_manager.UNKNOWN_CATEGORY_SENTINEL
    assert "Cannot classify command: categories are not loaded" in caplog.text

def test_add_command_no_callback(monkeypatch, caplog):
    """Test add_command without UI callback."""
    monkeypatch.setattr(category_manager, '_append_output_func_ref', None)
    category_manager.add_command_to_category("cmd", "1")
    assert "append_output function not available" in caplog.text

def test_remove_command_no_callback(monkeypatch, caplog):
    """Test remove_command without UI callback."""
    monkeypatch.setattr(category_manager, '_append_output_func_ref', None)
    category_manager.remove_command_from_category("cmd")
    assert "append_output function not available" in caplog.text
    
    # --- New Tests for Enhanced Coverage ---
    
    
    
    @patch("modules.category_manager._load_single_category_file")
    
    @patch("modules.category_manager.config_handler.save_json_file")
    
    def test_load_and_merge_create_default_if_missing(mock_save, mock_load_single, monkeypatch):
    
        monkeypatch.setattr(category_manager, 'DEFAULT_CATEGORY_FILE_PATH', '/tmp/default.json')
    
        monkeypatch.setattr(category_manager, 'USER_CATEGORY_FILE_PATH', '/tmp/user.json')
    
        
    
        with patch("os.path.exists", side_effect=[False]): # Default file missing
    
            mock_load_single.side_effect = [
    
                {}, # Default loaded (empty after creation attempt)
    
                {}  # User loaded
    
            ]
    
            mock_save.return_value = True
    
            
    
            category_manager.load_and_merge_command_categories()
    
            
    
            # Should attempt to save empty structure to default path
    
            mock_save.assert_called_once()
    
            args = mock_save.call_args
    
            assert args[0][0] == '/tmp/default.json'
    
            assert "simple" in args[0][1]
    
    
    
    @patch("modules.category_manager._load_single_category_file")
    
    
    
    def test_load_and_merge_logic(mock_load_single, monkeypatch):
    
    
    
        monkeypatch.setattr(category_manager, 'DEFAULT_CATEGORY_FILE_PATH', '/d')
    
    
    
        monkeypatch.setattr(category_manager, 'USER_CATEGORY_FILE_PATH', '/u')
    
    
    
    
    
    
    
    def test_add_command_empty(monkeypatch):
    
        mock_append = MagicMock()
    
        monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
        category_manager.add_command_to_category("", "simple")
    
        mock_append.assert_called_with("⚠️ Cannot add empty command.", style_class='warning')
    
    
    
    def test_add_command_invalid_category(monkeypatch):
    
        mock_append = MagicMock()
    
        monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
        category_manager.add_command_to_category("cmd", "invalid_cat")
    
        mock_append.assert_called_with("❌ Invalid category: 'invalid_cat'.", style_class='error')
    
    
    
    @patch("modules.category_manager._load_single_category_file")
    
    def test_add_command_already_exists_same_category(mock_load, monkeypatch):
    
        mock_load.return_value = {"simple": ["cmd"], "semi_interactive": []}
    
        mock_append = MagicMock()
    
        monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
        
    
        if not category_manager.CATEGORY_MAP:
    
             category_manager.CATEGORY_MAP = {"simple": "simple"}
    
    
    
        category_manager.add_command_to_category("cmd", "simple")
    
        mock_append.assert_called_with("ℹ️ Command 'cmd' is already set as 'simple'.", style_class='info')
    
    
    
    @patch("modules.category_manager._load_single_category_file")
    
    @patch("modules.category_manager._save_user_command_categories")
    
    @patch("modules.category_manager.load_and_merge_command_categories")
    
    def test_add_command_move_category(mock_merge, mock_save, mock_load, monkeypatch):
    
        # Command starts in simple, we move to semi_interactive
    
        mock_load.return_value = {"simple": ["cmd"], "semi_interactive": []}
    
        mock_append = MagicMock()
    
        monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
        
    
        if not category_manager.CATEGORY_MAP:
    
             category_manager.CATEGORY_MAP = {"simple": "simple", "semi_interactive": "semi_interactive"}
    
    
    
        category_manager.add_command_to_category("cmd", "semi_interactive")
    
        
    
        saved_data = mock_save.call_args[0][0]
    
        assert "cmd" not in saved_data["simple"]
    
        assert "cmd" in saved_data["semi_interactive"]
    
        mock_append.assert_any_call("✅ Command 'cmd' moved from 'simple' to 'semi_interactive'.", style_class='success')
    
    
    
    def test_remove_command_empty(monkeypatch):
    
        mock_append = MagicMock()
    
        monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
        category_manager.remove_command_from_category("")
    
        mock_append.assert_called_with("⚠️ Cannot remove empty command.", style_class='warning')
    
    
    
    def test_handle_command_subsystem_shlex_error(monkeypatch):
    
        mock_append = MagicMock()
    
        monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
        category_manager.handle_command_subsystem_input('/command add "unclosed quote')
    
        mock_append.assert_called()
    
        assert "Error parsing /command" in mock_append.call_args[0][0]
    
    
    
    def test_handle_command_subsystem_run_invalid_cat(monkeypatch):
    
        mock_append = MagicMock()
    
        monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
        category_manager.handle_command_subsystem_input('/command run invalid "cmd"')
    
        mock_append.assert_called_with("❌ Invalid category for 'run': 'invalid'.", style_class='error')
    
    
    
    def test_handle_command_subsystem_add_usage_error(monkeypatch):
    
        mock_append = MagicMock()
    
        monkeypatch.setattr(category_manager, '_append_output_func_ref', mock_append)
    
        category_manager.handle_command_subsystem_input('/command add "only_one_arg"')
    
        mock_append.assert_called()
    
        assert "Usage: /command add" in mock_append.call_args[0][0]
    
    
    