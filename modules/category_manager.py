# --- API DOCUMENTATION for modules/category_manager.py ---
#
# **Purpose:** Manages the classification of shell commands into execution categories
# (simple, semi_interactive, interactive_tui) by merging default and user configurations.
#
# **Public Functions:**
#
# def init_category_manager(script_dir_path: str, config_dir_name: str, append_output_func_ref: callable):
#     """
#     Initializes the manager with necessary paths and the UI callback function.
#
#     Must be called once at startup from main.py before any other functions
#     in this module are used. It loads and merges the initial categories.
#
#     Args:
#         script_dir_path (str): The absolute path to the main script's directory.
#         config_dir_name (str): The name of the configuration directory (e.g., "config").
#         append_output_func_ref (callable): A reference to UIManager.append_output
#                                            to display messages to the user.
#     """
#
# def classify_command(cmd: str) -> str:
#     """
#     Classifies a given command string based on the loaded categories.
#
#     Returns the category name (e.g., "simple") if found, otherwise returns
#     the UNKNOWN_CATEGORY_SENTINEL.
#
#     Args:
#         cmd (str): The full command string to classify.
#
#     Returns:
#         str: The name of the category or the UNKNOWN_CATEGORY_SENTINEL constant.
#     """
#
# def add_command_to_category(full_cmd_to_add: str, category_input: str):
#     """
#     Adds a command to a specified category in the user's configuration file.
#
#     This function handles saving the change to user_command_categories.json and
#     then re-merging all categories to reflect the change immediately.
#
#     Args:
#         full_cmd_to_add (str): The command string to add or update.
#         category_input (str): The target category (e.g., "simple", "2").
#     """
#
# def handle_command_subsystem_input(input_str: str) -> dict | None:
#     """
#     Parses and handles all '/command' subcommands (add, remove, list, move, run).
#
#     This function is the entry point for the `/command` built-in. It prints
#     help/lists directly to the UI. For the 'run' action, it returns a
#     dictionary instructing the shell_engine to execute a command.
#
#     Args:
#         input_str (str): The full user input string, starting with "/command".
#
#     Returns:
#         dict | None: Returns a dictionary {'action': 'force_run', ...} if the
#                      subcommand was 'run'. Returns None for all other cases.
#     """
#
# **Key Global Constants/Variables:**
# - UNKNOWN_CATEGORY_SENTINEL: A string constant ("##UNKNOWN_CATEGORY##") returned by
#                            classify_command when a command is not found.
# - CATEGORY_MAP: A dictionary mapping user-friendly inputs (e.g., "1") to
#                 category names ("simple"). Used by main.py for UI prompts.
# - CATEGORY_DESCRIPTIONS: A dictionary with descriptions for each category name.
#                          Used by main.py for UI prompts.
#
# --- END API DOCUMENTATION ---

# modules/category_manager.py

import os
import sys
import json
import shlex
import logging

# --- New Import ---
from modules import config_handler

# --- Module-specific logger ---
logger = logging.getLogger(__name__)

# --- Module-level "global" variables (initialized via init_category_manager) ---
_SCRIPT_DIR_PATH = None
_CONFIG_DIR_NAME_CONST = None # e.g., "config"
_append_output_func_ref = None # Reference to main.append_output

# --- Constants to be used by this module and potentially imported by main.py ---
DEFAULT_CATEGORY_FILENAME = "default_command_categories.json"
USER_CATEGORY_FILENAME = "user_command_categories.json"
UNKNOWN_CATEGORY_SENTINEL = "##UNKNOWN_CATEGORY##"

# --- Path variables, constructed during initialization ---
DEFAULT_CATEGORY_FILE_PATH = None
USER_CATEGORY_FILE_PATH = None

# --- Core category data structures ---
# These can be imported by main.py for display or logic if needed
CATEGORY_MAP = {
    "1": "simple", "2": "semi_interactive", "3": "interactive_tui",
    "simple": "simple", "semi_interactive": "semi_interactive", "interactive_tui": "interactive_tui",
}
CATEGORY_DESCRIPTIONS = {
    "simple": "Direct output in micro_X",
    "semi_interactive": "Output in micro_X after tmux run (may be interactive)",
    "interactive_tui": "Full interactive tmux session"
}
_CURRENTLY_LOADED_CATEGORIES = {} # Internal cache for merged categories


def init_category_manager(script_dir_path: str, config_dir_name: str, append_output_func_ref):
    """
    Initializes the category manager with necessary paths and callback functions.
    This must be called once from main.py at startup.
    """
    global _SCRIPT_DIR_PATH, _CONFIG_DIR_NAME_CONST, _append_output_func_ref
    global DEFAULT_CATEGORY_FILE_PATH, USER_CATEGORY_FILE_PATH

    _SCRIPT_DIR_PATH = script_dir_path
    _CONFIG_DIR_NAME_CONST = config_dir_name
    _append_output_func_ref = append_output_func_ref

    # Construct full paths to category files
    config_path_base = os.path.join(_SCRIPT_DIR_PATH, _CONFIG_DIR_NAME_CONST)
    DEFAULT_CATEGORY_FILE_PATH = os.path.join(config_path_base, DEFAULT_CATEGORY_FILENAME)
    USER_CATEGORY_FILE_PATH = os.path.join(config_path_base, USER_CATEGORY_FILENAME)

    logger.info(f"Category manager initialized. Default categories: {DEFAULT_CATEGORY_FILE_PATH}, User categories: {USER_CATEGORY_FILE_PATH}")
    load_and_merge_command_categories() # Perform initial load


def _load_single_category_file(file_path: str) -> dict:
    """Loads a single category JSON file using the config_handler, ensuring structure."""
    loaded_data = config_handler.load_jsonc_file(file_path)
    
    if loaded_data is None:
        # If file doesn't exist or is invalid, return a default empty structure
        return {cat_name: [] for cat_name in set(CATEGORY_MAP.values())}

    categories = {}
    # Ensure all defined categories in CATEGORY_MAP.values() exist as keys
    for cat_name_key in set(CATEGORY_MAP.values()):
        if cat_name_key not in loaded_data:
            categories[cat_name_key] = [] # Initialize if missing
        elif not isinstance(loaded_data[cat_name_key], list):
            logger.warning(f"Category '{cat_name_key}' in {file_path} is not a list. Resetting to empty list.")
            categories[cat_name_key] = []
        else:
            # Ensure all commands are strings
            categories[cat_name_key] = [str(cmd) for cmd in loaded_data[cat_name_key] if isinstance(cmd, str)]
            
    logger.info(f"Successfully loaded and validated categories from {file_path}")
    return categories


def load_and_merge_command_categories():
    """Loads default and user categories, merges them, and updates the internal cache."""
    global _CURRENTLY_LOADED_CATEGORIES
    if DEFAULT_CATEGORY_FILE_PATH is None or USER_CATEGORY_FILE_PATH is None:
        logger.error("Category paths not initialized. Call init_category_manager first.")
        return

    default_categories = _load_single_category_file(DEFAULT_CATEGORY_FILE_PATH)
    
    # If default category file doesn't exist, try to create an empty one
    if not os.path.exists(DEFAULT_CATEGORY_FILE_PATH): 
        logger.info(f"{DEFAULT_CATEGORY_FILENAME} not found at {DEFAULT_CATEGORY_FILE_PATH}. Attempting to create an empty one.")
        empty_data = {cat_name: [] for cat_name in set(CATEGORY_MAP.values())}
        if config_handler.save_json_file(DEFAULT_CATEGORY_FILE_PATH, empty_data):
            logger.info(f"Created empty default category file: {DEFAULT_CATEGORY_FILE_PATH}")
        else:
            logger.error(f"Could not create empty {DEFAULT_CATEGORY_FILENAME} at {DEFAULT_CATEGORY_FILE_PATH}")

    user_categories = _load_single_category_file(USER_CATEGORY_FILE_PATH)
    
    # Start with a deep copy of default categories
    merged_categories = {k: list(v) for k, v in default_categories.items()} 
    
    # Merge user categories, ensuring user's choice overrides default and removes duplicates
    for category_name, user_cmds_in_category in user_categories.items():
        if category_name not in merged_categories:
            merged_categories[category_name] = [] 
        
        for user_cmd in user_cmds_in_category:
            # Remove command from any other category in merged_categories
            for cat_list_to_check in merged_categories.values(): 
                if user_cmd in cat_list_to_check:
                    cat_list_to_check.remove(user_cmd)
            
            # Add to the target category
            if user_cmd not in merged_categories[category_name]: 
                merged_categories[category_name].append(user_cmd)
                
    _CURRENTLY_LOADED_CATEGORIES = merged_categories
    logger.info("Default and user command categories have been loaded and merged.")


def classify_command(cmd: str) -> str:
    """Checks the loaded & merged categories to find the classification for a command."""
    if not _CURRENTLY_LOADED_CATEGORIES:
        logger.warning("Categories not loaded. Attempting to load now.")
        load_and_merge_command_categories()
        if not _CURRENTLY_LOADED_CATEGORIES:
            logger.error("Cannot classify command: categories are not loaded and path might be uninitialized.")
            return UNKNOWN_CATEGORY_SENTINEL
            
    if not cmd:
        return UNKNOWN_CATEGORY_SENTINEL
        
    for category_name, full_commands_in_category in _CURRENTLY_LOADED_CATEGORIES.items():
        if cmd in full_commands_in_category:
            return category_name
            
    return UNKNOWN_CATEGORY_SENTINEL


def _save_user_command_categories(user_data: dict):
    """Saves data to the user command categories JSON file using config_handler."""
    if USER_CATEGORY_FILE_PATH is None:
        logger.error("User category path not initialized. Cannot save.")
        if _append_output_func_ref:
            _append_output_func_ref("❌ Error: User category path not configured.", style_class='error')
        return

    if not config_handler.save_json_file(USER_CATEGORY_FILE_PATH, user_data):
        logger.error(f"Failed to save user categories to {USER_CATEGORY_FILE_PATH} via config_handler.")
        if _append_output_func_ref:
            _append_output_func_ref("❌ Error saving user categories.", style_class='error')
    else:
        logger.info(f"User command categories saved to {USER_CATEGORY_FILE_PATH}")


def add_command_to_category(full_cmd_to_add: str, category_input: str):
    """Adds or updates a command's category in the USER FILE and reloads categories."""
    if not _append_output_func_ref:
        logger.warning("append_output function not available for add_command_to_category status messages.")
    
    if not full_cmd_to_add:
        if _append_output_func_ref: _append_output_func_ref("⚠️ Cannot add empty command.", style_class='warning')
        logger.warning("Attempted to add an empty command to categories.")
        return 

    target_category_name = CATEGORY_MAP.get(category_input.lower())
    if not target_category_name:
        if _append_output_func_ref: _append_output_func_ref(f"❌ Invalid category: '{category_input}'.", style_class='error')
        logger.warning(f"Invalid category specified for adding command: {category_input}")
        return 

    user_categories = _load_single_category_file(USER_CATEGORY_FILE_PATH)
    cmd_found_in_user_file_old_cat = None

    for cat_name, cmds_list in user_categories.items(): 
        if full_cmd_to_add in cmds_list:
            if cat_name != target_category_name:
                cmds_list.remove(full_cmd_to_add)
                cmd_found_in_user_file_old_cat = cat_name
            else:
                if _append_output_func_ref: _append_output_func_ref(f"ℹ️ Command '{full_cmd_to_add}' is already set as '{target_category_name}'.", style_class='info')
                logger.info(f"Command '{full_cmd_to_add}' already in user category '{target_category_name}'. No change needed.")
                return 
                
    if full_cmd_to_add not in user_categories[target_category_name]:
        user_categories[target_category_name].append(full_cmd_to_add)
    
    _save_user_command_categories(user_categories)
    load_and_merge_command_categories()
    
    if _append_output_func_ref:
        if cmd_found_in_user_file_old_cat:
            _append_output_func_ref(f"✅ Command '{full_cmd_to_add}' moved from '{cmd_found_in_user_file_old_cat}' to '{target_category_name}'.", style_class='success') 
        else:
            _append_output_func_ref(f"✅ Command '{full_cmd_to_add}' now set as '{target_category_name}'.", style_class='success') 
    logger.info(f"Command '{full_cmd_to_add}' added/updated to category '{target_category_name}' in user settings.")


def remove_command_from_category(full_cmd_to_remove: str):
    """Removes a command from the user's explicit categorizations and reloads."""
    if not _append_output_func_ref:
        logger.warning("append_output function not available for remove_command_from_category status messages.")

    if not full_cmd_to_remove:
        if _append_output_func_ref: _append_output_func_ref("⚠️ Cannot remove empty command.", style_class='warning')
        logger.warning("Attempted to remove an empty command from categories.")
        return 

    user_categories = _load_single_category_file(USER_CATEGORY_FILE_PATH)
    found_and_removed_from_user = False
    
    for commands_in_category in user_categories.values():
        if full_cmd_to_remove in commands_in_category:
            commands_in_category.remove(full_cmd_to_remove)
            found_and_removed_from_user = True
            
    if found_and_removed_from_user:
        _save_user_command_categories(user_categories)
        load_and_merge_command_categories()
        if _append_output_func_ref: _append_output_func_ref(f"🗑️ Command '{full_cmd_to_remove}' removed from your user settings.", style_class='info') 
        logger.info(f"Command '{full_cmd_to_remove}' removed from user categories.")
    else:
        if _append_output_func_ref: _append_output_func_ref(f"⚠️ Command '{full_cmd_to_remove}' not found in your user settings.", style_class='warning')
        logger.info(f"Command '{full_cmd_to_remove}' not found in user categories for removal.")


def list_categorized_commands():
    """Displays all categorized commands (merged view) using the append_output_func."""
    if not _append_output_func_ref:
        logger.error("append_output function not available. Cannot list categories to UI.")
        return

    if not _CURRENTLY_LOADED_CATEGORIES:
        logger.warning("Categories not loaded. Attempting to load for listing.")
        load_and_merge_command_categories()
        if not _CURRENTLY_LOADED_CATEGORIES:
            _append_output_func_ref("❌ Error: Categories could not be loaded for listing.", style_class='error')
            return

    _append_output_func_ref("📄 Current command categories (defaults + user overrides):", style_class='info-header') 
    
    sorted_category_names = sorted(list(set(CATEGORY_MAP.values())))

    for cat_name in sorted_category_names:
        full_commands_in_cat = sorted(_CURRENTLY_LOADED_CATEGORIES.get(cat_name, []))
        description = CATEGORY_DESCRIPTIONS.get(cat_name, 'No description')
        _append_output_func_ref(f"\n🔹 {cat_name} ({description}):", style_class='info-subheader') 
        
        if full_commands_in_cat:
            for cmd in full_commands_in_cat:
                _append_output_func_ref(f"  - {cmd}", style_class='info-item') 
        else:
            _append_output_func_ref("  (No commands in this category)", style_class='info-item-empty') 
    _append_output_func_ref("")


def move_command_category(full_cmd_to_move: str, new_category_input: str):
    """Moves a command to a new category in the user's settings. Essentially an alias for add."""
    logger.info(f"Moving command '{full_cmd_to_move}' to category '{new_category_input}'.")
    add_command_to_category(full_cmd_to_move, new_category_input)


def handle_command_subsystem_input(input_str: str):
    """
    Parses and handles '/command' subcommands.
    Returns a dictionary for 'run' action, None otherwise.
    """
    if not _append_output_func_ref:
        logger.error("append_output function not available for /command subsystem.")
        return None
        
    try:
        parts = shlex.split(input_str.strip())
    except ValueError as e:
        _append_output_func_ref(f"❌ Error parsing /command: {e}", style_class='error')
        logger.warning(f"shlex error for /command '{input_str}': {e}")
        return None 

    cmd_help = (f"ℹ️ /command usage:\n" 
                f"  add \"<cmd>\" <cat>          - Add command to a category.\n"
                f"  remove \"<cmd>\"             - Remove command from your settings.\n"
                f"  list                       - List all categorized commands.\n"
                f"  move \"<cmd>\" <new_cat>     - Move command to a new category.\n"
                f"  run <cat_num|cat_name> \"<cmd>\" - Force run command with category.\n"
                f"  help                       - Show this help message.\n"
                f"Categories: 1/simple, 2/semi_interactive, 3/interactive_tui")

    if len(parts) < 2 or parts[0] != "/command":
        _append_output_func_ref(f"❌ Invalid /command structure.\n{cmd_help}", style_class='error')
        return None 
        
    subcmd = parts[1].lower()
    
    if subcmd == "add":
        if len(parts) == 4:
            add_command_to_category(parts[2], parts[3])
        else:
            _append_output_func_ref(f"❌ Usage: /command add \"<full_command_string>\" <category>", style_class='error') 
    elif subcmd == "remove":
        if len(parts) == 3:
            remove_command_from_category(parts[2])
        else:
            _append_output_func_ref(f"❌ Usage: /command remove \"<full_command_string>\"", style_class='error') 
    elif subcmd == "list":
        if len(parts) == 2:
            list_categorized_commands()
        else:
            _append_output_func_ref(f"❌ Usage: /command list", style_class='error') 
    elif subcmd == "move":
        if len(parts) == 4:
            move_command_category(parts[2], parts[3])
        else:
            _append_output_func_ref(f"❌ Usage: /command move \"<full_command_string>\" <new_category>", style_class='error') 
    elif subcmd == "run":
        if len(parts) == 4:
            category_input = parts[2]
            command_to_run = parts[3]
            
            resolved_category = CATEGORY_MAP.get(category_input.lower())
            if not resolved_category:
                 _append_output_func_ref(f"❌ Invalid category for 'run': '{category_input}'.", style_class='error')
                 return None
            
            logger.info(f"/command run: category '{resolved_category}', command '{command_to_run}'")
            return {'action': 'force_run', 'command': command_to_run, 'category': resolved_category}
        else:
            _append_output_func_ref(f"❌ Usage: /command run <category> \"<full_command_string>\"", style_class='error')
    elif subcmd == "help":
        _append_output_func_ref(cmd_help, style_class='help-base') 
    else:
        _append_output_func_ref(f"❌ Unknown /command subcommand '{subcmd}'.\n{cmd_help}", style_class='error')
    
    return None
