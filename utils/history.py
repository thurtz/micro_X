#!/usr/bin/env python

import os
import argparse

HELP_TEXT = """
Displays the command history for the micro_X shell.

USAGE:
  /history [-n <lines>] [--all]

OPTIONS:
  -n, --lines <number>   Number of recent history lines to display. Defaults to 100.
  --all                  Display all history, overriding any line limit.
"""

def display_history(history_file_path, num_lines=None, show_all=False):
    """Reads and displays the command history from the given file."""
    try:
        with open(history_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        all_commands = [line[1:].strip() for line in lines if line.startswith('+')]

        if show_all:
            commands_to_display = all_commands
            start_index = 0
        else:
            # Default to 100 if no limit is provided
            limit = num_lines if num_lines is not None else 100
            if limit > 0:
                commands_to_display = all_commands[-limit:]
                start_index = len(all_commands) - len(commands_to_display)
            else:
                commands_to_display = []
                start_index = 0

        for i, command in enumerate(commands_to_display, start=start_index + 1):
            print(f"{i: >5}  {command}")

    except FileNotFoundError:
        print(f"Error: History file not found at {history_file_path}")
        return
    except Exception as e:
        print(f"An error occurred: {e}")
        return

def main():
    """Main function to parse arguments and display history."""
    parser = argparse.ArgumentParser(
        description="Displays the command history for the micro_X shell. Defaults to the last 100 lines.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '-n', '--lines',
        type=int,
        help='Number of recent history lines to display.'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Display all history, overriding any line limit.'
    )

    args = parser.parse_args()

    # The history file is located in the parent directory of the 'utils' directory
    script_path = os.path.abspath(__file__)
    utils_dir = os.path.dirname(script_path)
    project_root = os.path.dirname(utils_dir)
    history_file = os.path.join(project_root, '.micro_x_history')

    display_history(history_file, num_lines=args.lines, show_all=args.all)

if __name__ == "__main__":
    main()
