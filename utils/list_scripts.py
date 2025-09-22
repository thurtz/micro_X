#!/usr/bin/env python

import os
import sys
import argparse
import json # Added for alias handling

# --- Path Setup ---
# Add the project root to the Python path to allow importing from 'modules'
try:
    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(script_path))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from modules import config_handler
except ImportError as e:
    print(f"❌ Error: Could not import the config_handler module. Ensure this script is run from within the micro_X project structure.", file=sys.stderr)
    print(f"   Details: {e}", file=sys.stderr)
    sys.exit(1)

# --- Configuration ---
UTILS_DIR_NAME = "utils"
USER_SCRIPTS_DIR_NAME = "user_scripts"

# Alias Configuration
DEFAULT_ALIASES_FILENAME = "default_aliases.json"
USER_ALIASES_FILENAME = "user_aliases.json"
CONFIG_DIR_NAME = "config"

# --- Helper Functions ---
def get_project_root():
    """Determines the project root directory."""
    script_path = os.path.abspath(__file__)
    # Assumes this script is in project_root/utils/
    return os.path.dirname(os.path.dirname(script_path))

def get_scripts_from_directory(directory_path):
    """Scans a directory for .py files and returns their base names."""
    if not os.path.isdir(directory_path):
        return []
    try:
        scripts = [
            f[:-3] for f in os.listdir(directory_path)
            if os.path.isfile(os.path.join(directory_path, f))
            and f.endswith(".py")
            and f != "__init__.py"
        ]
        return sorted(scripts)
    except OSError as e:
        print(f"Error reading directory {directory_path}: {e}", file=sys.stderr)
        return []

def load_aliases(aliases_path):
    """Loads an alias file using the centralized config handler."""
    aliases = config_handler.load_jsonc_file(aliases_path)
    if aliases is None:
        return {}  # Return an empty dict if file doesn't exist or is invalid
    if not isinstance(aliases, dict):
        # In a CLI tool, we might just print a warning or ignore, not necessarily log
        print(f"Warning: Alias file at {aliases_path} is not a valid dictionary. Ignoring.", file=sys.stderr)
        return {}
    return aliases

def main():
    """Main function to list all available scripts."""
    parser = argparse.ArgumentParser(
        description="Lists all available built-in utilities, custom user scripts, and aliases for micro_X."
    )
    parser.add_argument(
        '--type',
        choices=['all', 'scripts', 'utils', 'aliases'],
        default='all',
        help='Filter by type: "all", "scripts", "utils", or "aliases".'
    )
    parser.add_argument(
        '--name',
        type=str,
        help='Filter by name (case-insensitive substring match).'
    )
    args = parser.parse_args()

    project_root = get_project_root()
    utils_path = os.path.join(project_root, UTILS_DIR_NAME)
    user_scripts_path = os.path.join(project_root, USER_SCRIPTS_DIR_NAME)
    config_dir = os.path.join(project_root, CONFIG_DIR_NAME)
    default_aliases_path = os.path.join(config_dir, DEFAULT_ALIASES_FILENAME)
    user_aliases_path = os.path.join(config_dir, USER_ALIASES_FILENAME)

    util_scripts = get_scripts_from_directory(utils_path)
    user_scripts = get_scripts_from_directory(user_scripts_path)

    default_aliases = load_aliases(default_aliases_path)
    user_aliases = load_aliases(user_aliases_path)
    all_aliases = {**default_aliases, **user_aliases} # User aliases override defaults

    print("\nAvailable Commands in micro_X")
    print("=" * 30)

    name_filter = args.name.lower() if args.name else None

    if args.type in ['all', 'utils']:
        print("\n--- Built-in Utilities (run with /utils <name>) ---")
        filtered_utils = [s for s in util_scripts if not name_filter or name_filter in s.lower()]
        if filtered_utils:
            for script in filtered_utils:
                print(f"  - {script}")
        else:
            print("  (No utilities found matching criteria)")

    if args.type in ['all', 'scripts']:
        print("\n--- User Scripts (run with /run <name>) ---")
        filtered_scripts = [s for s in user_scripts if not name_filter or name_filter in s.lower()]
        if filtered_scripts:
            for script in filtered_scripts:
                print(f"  - {script}")
        else:
            print(f"  (No scripts found in '{USER_SCRIPTS_DIR_NAME}/' directory matching criteria)")
            if not name_filter:
                print("  You can add your own .py files to this directory.")

    if args.type in ['all', 'aliases']:
        print("\n--- Aliases (run with <alias_name>) ---")
        filtered_aliases = {
            alias: command for alias, command in all_aliases.items()
            if not name_filter or name_filter in alias.lower() or name_filter in command.lower()
        }
        if filtered_aliases:
            max_alias_len = max(len(alias) for alias in filtered_aliases.keys()) if filtered_aliases else 0
            for alias, command in sorted(filtered_aliases.items()):
                source = " (user)" if alias in user_aliases else " (default)"
                print(f"  {alias:<{max_alias_len}}  ->  {command}{source}")
        else:
            print("  (No aliases found matching criteria)")

    print("\n" + "=" * 30)


if __name__ == "__main__":
    main()
