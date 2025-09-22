#!/usr/bin/env python

import os
import sys
import argparse

# --- Path Setup ---
# Add the utils directory to the Python path to allow importing from 'shared'
try:
    script_path = os.path.abspath(__file__)
    utils_dir = os.path.dirname(script_path)
    if utils_dir not in sys.path:
        sys.path.insert(0, utils_dir)
    # Now we can safely import from shared
    from shared.helpers import get_project_root, load_json_file, save_json_file, logger, format_aliases_list
    from shared.consts import *
except ImportError as e:
    print(f"❌ Error: Could not import the shared module. Ensure this script is run from within the micro_X project structure.", file=sys.stderr)
    print(f"   Details: {e}", file=sys.stderr)
    sys.exit(1)

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

    user_aliases = load_json_file(user_aliases_path)
    
    user_aliases[alias_name] = command
    if save_json_file(user_aliases_path, user_aliases):
        print(f"✅ User alias '{alias_name}' successfully mapped to '{command}'.")

def handle_remove_alias(args, user_aliases_path):
    """Handles the --remove alias command from the user aliases file."""
    alias_name = args.remove

    if not alias_name.startswith('/'):
        print("❌ Error: Alias name must begin with a forward slash '/'.", file=sys.stderr)
        return

    user_aliases = load_json_file(user_aliases_path)

    if alias_name in user_aliases:
        del user_aliases[alias_name]
        if save_json_file(user_aliases_path, user_aliases):
            print(f"🗑️ User alias '{alias_name}' successfully removed.")
            print("   (If a default alias with the same name exists, it will now be active).")
    else:
        print(f"⚠️ Warning: Alias '{alias_name}' not found in your user-defined aliases.", file=sys.stderr)

def handle_list_aliases(default_path, user_path):
    """Handles the --list alias command, showing merged results."""
    default_aliases = load_json_file(default_path)
    user_aliases = load_json_file(user_path)
    merged_aliases = {**default_aliases, **user_aliases}
    print(format_aliases_list(merged_aliases, user_aliases))

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