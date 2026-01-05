#!/usr/bin/env python

import argparse
import os
import subprocess
import sys

HELP_TEXT = '''
micro_X Help: /logs Command

Usage: /logs [options]

  Tails the micro_X log file for a specified branch. If no branch is specified, it defaults to the current branch.

Options:
  --main      Tail logs from the main branch.
  --testing   Tail logs from the testing branch.
  --dev       Tail logs from the dev branch.
  -h, --help  Show this help message.

Examples:
  /logs           - Tails the logs of the current branch.
  /logs --main    - Tails the logs of the main branch.
  /logs --dev     - Tails the logs of the dev branch.
'''

# Define the root directory for the micro_X project structure.
# os.path.expanduser("~") ensures the home directory is correctly resolved.
ROOT_DIR = os.path.abspath(os.path.join(os.path.expanduser("~"), "micro_X"))

# Define the directory names for each branch relative to the root.
# The main branch is the ROOT_DIR itself.
BRANCH_DIRS = {
    "main": ROOT_DIR,
    "testing": os.path.join(ROOT_DIR, "micro_X-testing"),
    "dev": os.path.join(ROOT_DIR, "micro_X-dev"),
}
LOG_FILE_NAME = "logs/micro_x.log"

def get_current_branch():
    """
    Gets the current git branch name.
    Returns the branch name as a string, or None if not in a git repository
    or if an error occurs.
    """
    try:
        # We run this from the current script's directory context.
        # The CWD should be within the dev repo.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir) # up one level from utils

        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # If git command fails or isn't found, we can't determine the branch.
        return None

def main():
    """
    Main function to parse arguments and tail the appropriate log file.
    """
    parser = argparse.ArgumentParser(
        description="Tail micro_X logs for different branches. Defaults to the current branch."
    )
    parser.add_argument(
        "--main",
        action="store_true",
        help="Tail logs from the main branch."
    )
    parser.add_argument(
        "--testing",
        action="store_true",
        help="Tail logs from the testing branch."
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Tail logs from the dev branch."
    )

    args = parser.parse_args()

    target_branch = None
    if args.main:
        target_branch = "main"
    elif args.testing:
        target_branch = "testing"
    elif args.dev:
        target_branch = "dev"
    else:
        # No flag provided, so determine branch automatically.
        target_branch = get_current_branch()
        if target_branch not in BRANCH_DIRS:
            # If it's a feature branch or something else, default to 'dev'
            # since all development happens in that directory.
            print(f"Info: Current branch '{target_branch}' is not a primary branch. Defaulting to 'dev' logs.")
            target_branch = "dev"

    if not target_branch:
        print("Error: Could not determine git branch and no branch flag was provided.", file=sys.stderr)
        print("Please run this from within the micro_X-dev git repository or use a flag like --dev.", file=sys.stderr)
        sys.exit(1)

    log_dir = BRANCH_DIRS.get(target_branch)
    if not log_dir:
        print(f"Error: Unknown branch '{target_branch}'.", file=sys.stderr)
        sys.exit(1)

    log_path = os.path.join(log_dir, LOG_FILE_NAME)

    if not os.path.exists(log_path):
        print(f"Error: Log file not found at: {log_path}", file=sys.stderr)
        sys.exit(1)

    try:
        print(f"Tailing log file: {log_path}")
        print("Press Ctrl+C to stop.")
        subprocess.run(["tail", "-f", log_path], check=True)
    except KeyboardInterrupt:
        print("\nStopped tailing log.")
    except FileNotFoundError:
        print("Error: 'tail' command not found. Please ensure it is installed and in your PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error tailing log file: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
