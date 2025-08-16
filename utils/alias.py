#!/usr/bin/env python

import os
import sys
import json
import argparse
import logging

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
    """Loads a single alias file from the JSON file."""
    if not os.path.exists(aliases_path):
        return {}
    try:
        with open(aliases_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading aliases from {aliases_path}: {e}")
        print(f"❌ Error: Could not read or parse the aliases file at {aliases_path}.", file=sys.stderr)
        return None

def load_and_merge_aliases(default_path, user_path):
    """Loads default and user aliases and merges them."""
    default_aliases = load_aliases(default_path)
    if default_aliases is None: default_aliases = {} # Recover from bad default file
    
    user_aliases = load_aliases(user_path)
    if user_aliases is None: user_aliases = {} # Recover from bad user file

    # User aliases override default aliases
    merged = {**default_aliases, **user_aliases}
    return merged

def save_aliases(aliases_path, aliases_data):
    """Saves aliases to the JSON file."""
    try:
        os.makedirs(os.path.dirname(aliases_path), exist_ok=True)
        with open(aliases_path, 'w', encoding='utf-8') as f:
            json.dump(aliases_data, f, indent=2, sort_keys=True)
        return True
    except IOError as e:
        logger.error(f"Error saving aliases to {aliases_path}: {e}")
        print(f"❌ Error: Could not write to the aliases file at {aliases_path}.", file=sys.stderr)
        return False

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
    if user_aliases is None: return

    user_aliases[alias_name] = command
    if save_aliases(user_aliases_path, user_aliases):
        print(f"✅ User alias '{alias_name}' successfully mapped to '{command}'.")

def handle_remove_alias(args, user_aliases_path):
    """Handles the --remove alias command from the user aliases file."""
    alias_name = args.remove

    if not alias_name.startswith('/'):
        print("❌ Error: Alias name must begin with a forward slash '/'.", file=sys.stderr)
        return

    user_aliases = load_aliases(user_aliases_path)
    if user_aliases is None: return

    if alias_name in user_aliases:
        del user_aliases[alias_name]
        if save_aliases(user_aliases_path, user_aliases):
            print(f"🗑️ User alias '{alias_name}' successfully removed.")
            print("   (If a default alias with the same name exists, it will now be active).")
    else:
        print(f"⚠️ Warning: Alias '{alias_name}' not found in your user-defined aliases.", file=sys.stderr)

def handle_list_aliases(default_path, user_path):
    """Handles the --list alias command, showing merged results."""
    default_aliases = load_aliases(default_path) or {}
    user_aliases = load_aliases(user_path) or {}
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
