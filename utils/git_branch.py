# utils/git_branch.py

import subprocess
import sys
import argparse

# --- Help Text ---
HELP_TEXT = """
micro_X Help: /git_branch Utility

This utility prints the current git branch name.

Usage:
  /git_branch
"""

def get_current_branch():
    """Prints the current git branch name."""
    try:
        # Using subprocess.run to capture output
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True  # Raises CalledProcessError if git command fails
        )
        current_branch = result.stdout.strip()
        print(f"Current Git Branch: {current_branch}")
    except FileNotFoundError:
        print("❌ Error: 'git' command not found. Is Git installed and in your PATH?", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        # This can happen if not in a git repository
        error_message = e.stderr.strip()
        print(f"❌ Error: Not a git repository or another git error occurred.\n   Details: {error_message}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    """
    Main function to parse arguments and execute logic.
    """
    class HelpAction(argparse.Action):
        def __init__(self, option_strings, dest, **kwargs):
            super(HelpAction, self).__init__(option_strings, dest, nargs=0, **kwargs)
        def __call__(self, parser, namespace, values, option_string=None):
            print(HELP_TEXT)
            parser.exit()

    parser = argparse.ArgumentParser(
        description="Prints the current git branch name.",
        add_help=False
    )
    parser.add_argument('-h', '--help', action=HelpAction, help='show this help message and exit')

    # If no arguments are provided, run the script, otherwise print help
    if len(sys.argv) > 1:
        args = parser.parse_args()
    else:
        get_current_branch()

if __name__ == "__main__":
    main()