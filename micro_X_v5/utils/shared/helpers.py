#!/usr/bin/env python

import os
import sys
import logging

# --- Path Setup ---
# Add the project root to the Python path to allow importing from 'modules'
try:
    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_path)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    # Now we can safely import from modules
    from modules import config_handler
except ImportError as e:
    print(f"❌ Error: Could not import the config_handler module. Ensure this script is run from within the micro_X project structure.", file=sys.stderr)
    print(f"   Details: {e}", file=sys.stderr)
    sys.exit(1)

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def get_project_root():
    """Determines the project root directory."""
    script_path = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(os.path.dirname(script_path)))

def load_json_file(file_path):
    """Loads a JSON file using the centralized config handler."""
    data = config_handler.load_jsonc_file(file_path)
    if data is None:
        return {}  # Return an empty dict if file doesn't exist or is invalid
    if not isinstance(data, dict):
        logger.warning(f"JSON file at {file_path} is not a valid dictionary. Ignoring.")
        return {}
    return data

def save_json_file(file_path, data):
    """Saves data to a JSON file using the centralized config handler."""
    return config_handler.save_json_file(file_path, data)

def format_aliases_list(merged_aliases, user_aliases):
    """Formats a list of aliases for consistent output."""
    if not merged_aliases:
        return "  (No aliases defined)"

    output = ["--- Aliases (user aliases override defaults) ---"]
    max_alias_len = max(len(alias) for alias in merged_aliases.keys()) if merged_aliases else 0
    for alias, command in sorted(merged_aliases.items()):
        source = " (user)" if alias in user_aliases else " (default)"
        output.append(f"  {alias:<{max_alias_len}}  ->  {command}{source}")
    return "\n".join(output)
