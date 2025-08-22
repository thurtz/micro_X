#!/usr/bin/env python

import os
import sys
import argparse

# --- Configuration ---
UTILS_DIR_NAME = "utils"
USER_SCRIPTS_DIR_NAME = "user_scripts"

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

def main():
    """Main function to list all available scripts."""
    parser = argparse.ArgumentParser(
        description="Lists all available built-in utilities and custom user scripts for micro_X."
    )
    # This script doesn't need arguments, but argparse provides -h/--help handling.
    parser.parse_args()

    project_root = get_project_root()
    utils_path = os.path.join(project_root, UTILS_DIR_NAME)
    user_scripts_path = os.path.join(project_root, USER_SCRIPTS_DIR_NAME)

    util_scripts = get_scripts_from_directory(utils_path)
    user_scripts = get_scripts_from_directory(user_scripts_path)

    print("\nAvailable Scripts in micro_X")
    print("=" * 30)

    print("\n--- Built-in Utilities (run with /utils <name>) ---")
    if util_scripts:
        for script in util_scripts:
            print(f"  - {script}")
    else:
        print("  (No utilities found)")

    print("\n--- User Scripts (run with /run <name>) ---")
    if user_scripts:
        for script in user_scripts:
            print(f"  - {script}")
    else:
        print(f"  (No scripts found in '{USER_SCRIPTS_DIR_NAME}/' directory)")
        print("  You can add your own .py files to this directory.")

    print("\n" + "=" * 30)


if __name__ == "__main__":
    main()
