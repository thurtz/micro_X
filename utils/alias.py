#!/usr/bin/env python

import os
import sys
import argparse

# --- Help Text ---
HELP_TEXT = """
micro_X Help: Command Aliases

Aliases are shortcuts for longer or more complex commands. You can use them to save typing and streamline your workflow.

Managing Aliases:
  micro_X uses the '/alias' command to manage your shortcuts.

  /alias --list              - Shows all currently active aliases (both default and user-defined).
  /alias --add <alias> "<command>" - Creates a new user alias. E.g., /alias --add /snap "/utils generate_snapshot"
  /alias --remove <alias>    - Removes a user-defined alias.

Default vs. User Aliases:
  - Default aliases are built-in for convenience (e.g., /help, /command).
  - You can create your own in 'config/user_aliases.json' using the '/alias --add' command.
  - Your user aliases will always override any default alias with the same name.
"""

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
    class HelpAction(argparse.Action):
        def __init__(self, option_strings, dest, **kwargs):
            super(HelpAction, self).__init__(option_strings, dest, nargs=0, **kwargs)
        def __call__(self, parser, namespace, values, option_string=None):
            print(HELP_TEXT)
            parser.exit()

    parser = argparse.ArgumentParser(
        description="Manage command aliases for micro_X.",
        add_help=False
    )
    parser.add_argument('-h', '--help', action=HelpAction, help='show this help message and exit')

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

    # If no arguments are provided, print help text
    if len(sys.argv) == 1:
        print(HELP_TEXT)
        sys.exit(0)

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