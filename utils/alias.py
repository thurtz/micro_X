#!/usr/bin/env python

import os
import sys
import json
import argparse
import logging

# --- New Import ---
from modules import config_handler

# --- Configuration ---
DEFAULT_ALIASES_FILENAME = "default_aliases.json"
USER_ALIASES_FILENAME = "user_aliases.json"
CONFIG_DIR_NAME = "config"
RESERVED_COMMAND_NAMES = [
    "/ai", "/command", "/ollama", "/utils", "/update", "/help",
    "exit", "quit", "/exit", "/quit"
]

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def get_project_root():
    """Determines the project root directory."""
    script_path = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(script_path))

def load_aliases(aliases_path):
    """Loads an alias file using the centralized config handler."""
    aliases = config_handler.load_jsonc_file(aliases_path)
    if aliases is None:
        return {}  # Return an empty dict if file doesn't exist or is invalid
    if not isinstance(aliases, dict):
        logger.warning(f"Alias file at {aliases_path} is not a valid dictionary. Ignoring.")
        return {}
    return aliases

def save_user_aliases(aliases_path, aliases_data):
    """Saves user aliases using the centralized config handler."""
    return config_handler.save_json_file(aliases_path, aliases_data)

def handle_add_alias(args, user_aliases_path):
    """Handles the --add alias command, modifying only the user aliases."""
    alias_name = args.add[0]
    command = " ".join(args.add[1:])

    if not alias_name.startswith('/'):
        print("❌ Error: Alias name must begin with a forward slash '/'.", file=sys.stderr)
        return

    if alias_name in RESERVED_COMMAND_NAMES:
        print(f"❌ Error: Alias name '{alias_name}' is a reserved command and cannot be used.", file=sys.stderr)
        return

    if not command:
        print("❌ Error: The command for the alias cannot be empty.", file=sys.stderr)
        return

    user_aliases = load_aliases(user_aliases_path)
    
    user_aliases[alias_name] = command
    if save_user_aliases(user_aliases_path, user_aliases):
        print(f"✅ User alias '{alias_name}' successfully mapped to '{command}'.")

def handle_remove_alias(args, user_aliases_path):
    """Handles the --remove alias command from the user aliases file."""
    alias_name = args.remove

    if not alias_name.startswith('/'):
        print("❌ Error: Alias name must begin with a forward slash '/'.", file=sys.stderr)
        return

    user_aliases = load_aliases(user_aliases_path)

    if alias_name in user_aliases:
        del user_aliases[alias_name]
        if save_user_aliases(user_aliases_path, user_aliases):
            print(f"🗑️ User alias '{alias_name}' successfully removed.")
            print("   (If a default alias with the same name exists, it will now be active).")
    else:
        print(f"⚠️ Warning: Alias '{alias_name}' not found in your user-defined aliases.", file=sys.stderr)

def handle_list_aliases(default_path, user_path):
    """Handles the --list alias command, showing merged results."""
    default_aliases = load_aliases(default_path)
    user_aliases = load_aliases(user_path)
    merged_aliases = {**default_aliases, **user_aliases}

    if not merged_aliases:
        print("No aliases defined.")
        return

    print("📄 Current Aliases (User aliases override defaults):")
    max_alias_len = max(len(alias) for alias in merged_aliases.keys()) if merged_aliases else 0
    for alias, command in sorted(merged_aliases.items()):
        source = " (user)" if alias in user_aliases else "(default)"
        print(f"  {alias:<{max_alias_len}}  ->  {command}  {source}")

def main():
    """Main function to parse arguments and execute alias management."""
    parser = argparse.ArgumentParser(
        description="Manage command aliases for micro_X.",
        epilog="Use this utility to create shortcuts for longer or frequently used commands."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--add',
        nargs='+',
        metavar=('<alias_name>', '<command>'),
        help="Add or update a user-specific alias. E.g., --add /lsnap /utils generate_snapshot"
    )
    group.add_argument(
        '--remove',
        metavar='<alias_name>',
        help="Remove a user-specific alias."
    )
    group.add_argument(
        '--list',
        action='store_true',
        help="List all currently active aliases (defaults and user)."
    )

    args = parser.parse_args()

    project_root = get_project_root()
    config_dir = os.path.join(project_root, CONFIG_DIR_NAME)
    default_aliases_path = os.path.join(config_dir, DEFAULT_ALIASES_FILENAME)
    user_aliases_path = os.path.join(config_dir, USER_ALIASES_FILENAME)

    if args.add:
        handle_add_alias(args, user_aliases_path)
    elif args.remove:
        handle_remove_alias(args, user_aliases_path)
    elif args.list:
        handle_list_aliases(default_aliases_path, user_aliases_path)

if __name__ == "__main__":
    main()
