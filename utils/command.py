#!/usr/bin/env python

import os
import sys
import argparse
import logging

# --- Help Text ---
HELP_TEXT = """
micro_X Help: Command Categorization

micro_X categorizes commands to execute them in the most appropriate way. When you run an unknown command, you will be prompted to choose a category.

Categories:
  - simple: For quick commands with direct text output (e.g., ls, pwd, echo).
  - semi_interactive: For commands that run longer or have a lot of output (e.g., apt update, ping). They run in a managed tmux window, with output shown upon completion.
  - interactive_tui: For full-screen, interactive applications (e.g., nano, vim, htop, ssh). They take over the screen in a tmux window until you exit.

/command <subcommand>
  - The '/command' utility (an alias for '/utils command') allows you to manage your saved categorizations.
  - Usage:
    /command list                    - Shows all categorized commands.
    /command add "<cmd>" <category>  - Adds or updates a command's category.
    /command remove "<cmd>"          - Removes a command from your user settings.
    /command move "<cmd>" <new_cat>  - Moves a command to a different category.
"""

# --- Path Setup ---
# Add the project root to the Python path to allow importing from 'modules'
try:
    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(script_path))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from modules import category_manager
except ImportError as e:
    print(f"❌ Error: Could not import the category_manager module. Ensure this script is run from within the micro_X project structure.", file=sys.stderr)
    print(f"   Details: {e}", file=sys.stderr)
    sys.exit(1)

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Main Logic ---
def main():
    """Main function to parse arguments and execute command management."""
    class HelpAction(argparse.Action):
        def __init__(self, option_strings, dest, **kwargs):
            super(HelpAction, self).__init__(option_strings, dest, nargs=0, **kwargs)
        def __call__(self, parser, namespace, values, option_string=None):
            print(HELP_TEXT)
            parser.exit()

    # Initialize the category manager to load categories and set up paths
    # This is crucial for all other functions in the module to work correctly.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    category_manager.init_category_manager(project_root, "config", lambda msg, style_class='INFO': print(msg))

    parser = argparse.ArgumentParser(
        description="Manage command categorizations for micro_X.",
        add_help=False
    )
    parser.add_argument('-h', '--help', action=HelpAction, help='show this help message and exit')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--add',
        nargs=2,
        metavar=('<command_string>', '<category>'),
        help="Add or update a command's category in your user settings."
    )
    group.add_argument(
        '--remove',
        metavar='<command_string>',
        help="Remove a command from your user-defined categories."
    )
    group.add_argument(
        '--move',
        nargs=2,
        metavar=('<command_string>', '<new_category>'),
        help="Move a command to a new category (same as --add)."
    )
    group.add_argument(
        '--list',
        action='store_true',
        help="List all currently known commands and their categories."
    )

    # If no arguments are provided, print help text
    if len(sys.argv) == 1:
        print(HELP_TEXT)
        sys.exit(0)

    args = parser.parse_args()

    try:
        if args.add:
            command, category = args.add
            category_manager.add_command_to_category(command, category)
        elif args.remove:
            category_manager.remove_command_from_category(args.remove)
        elif args.move:
            command, new_category = args.move
            category_manager.move_command_category(command, new_category)
        elif args.list:
            category_manager.list_categorized_commands()
    except Exception as e:
        logger.error(f"An error occurred in the command utility: {e}", exc_info=True)
        print(f"❌ An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
