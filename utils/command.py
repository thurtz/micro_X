#!/usr/bin/env python

import os
import sys
import argparse
import logging

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
    # Initialize the category manager to load categories and set up paths
    # This is crucial for all other functions in the module to work correctly.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    category_manager.init_category_manager(project_root, "config", lambda msg, style_class='INFO': print(msg))

    parser = argparse.ArgumentParser(
        description="Manage command categorizations for micro_X.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  command.py --add \"htop\" interactive_tui\n"
            "  command.py --remove \"htop\"\n"
            "  command.py --move \"ls -l\" simple\n"
            "  command.py --list\n\n"
            "Categories can be specified by name (simple, semi_interactive, interactive_tui) or by number (1, 2, 3)."
        )
    )
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
    # The 'run' subcommand is handled by ShellEngine, so it's not needed here.

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
