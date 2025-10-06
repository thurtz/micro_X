#!/usr/bin/env python

import subprocess
import sys
import os
import logging
import argparse

# --- Help Text ---
HELP_TEXT = """
micro_X Help: /setup_dev_env Utility

This utility sets up the development environment by installing all dependencies, including both runtime and development requirements.

Usage:
  /setup_dev_env

This script is a convenience wrapper that calls the '/utils install_requirements --all' utility. It ensures that your environment is ready for development and for running tests.
"""

# Basic logger for this utility script
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    """
    Runs the main install_requirements.py script with flags to install
    all developer (and by implication, runtime) dependencies.
    """
    class HelpAction(argparse.Action):
        def __init__(self, option_strings, dest, **kwargs):
            super(HelpAction, self).__init__(option_strings, dest, nargs=0, **kwargs)
        def __call__(self, parser, namespace, values, option_string=None):
            print(HELP_TEXT)
            parser.exit()

    parser = argparse.ArgumentParser(
        description='Set up the development environment by installing all dependencies.',
        add_help=False
    )
    parser.add_argument('-h', '--help', action=HelpAction, help='show this help message and exit')

    # If no arguments are provided, run the script, otherwise print help
    if len(sys.argv) > 1:
        args = parser.parse_args()
    else:
        run_setup()

def run_setup():
    logger.info("Initiating developer environment setup...")
    try:
        # Determine the project root assuming this script is in project_root/utils/
        current_script_path = os.path.abspath(__file__)
        utils_dir = os.path.dirname(current_script_path)
        project_root = os.path.dirname(utils_dir)

        install_script_path = os.path.join(project_root, "utils", "install_requirements.py")

        if not os.path.isfile(install_script_path):
            logger.error(f"Main installation script not found at: {install_script_path}")
            print(f"❌ Error: Core installation script 'install_requirements.py' not found in 'utils/' directory.", file=sys.stderr)
            sys.exit(1)

        # Arguments to pass to install_requirements.py.
        # Using '--all' assumes install_requirements.py handles this to install both
        # runtime and development dependencies.
        install_args = ["--all"]
        command_to_execute = [sys.executable, install_script_path] + install_args

        logger.info(f"Executing: {' '.join(command_to_execute)} from project root: {project_root}")
        print(f"⚙️ Calling '{os.path.basename(install_script_path)} {' '.join(install_args)}' to install all dependencies...")

        process = subprocess.run(
            command_to_execute,
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False # We'll check returncode manually to provide more context
        )

        if process.stdout:
            print("--- Output from dependency installation ---")
            print(process.stdout.strip())
        
        if process.stderr:
            # stderr from pip can sometimes be verbose even on success (e.g., warnings)
            # so we print it but don't necessarily treat all stderr as a hard failure initially.
            print("--- Errors/Warnings from dependency installation ---", file=sys.stderr)
            print(process.stderr.strip(), file=sys.stderr)

        if process.returncode == 0:
            logger.info("Developer environment setup completed successfully.")
            print("✅ Developer dependencies (and runtime) should now be installed.")
        else:
            logger.error(f"Dependency installation script failed with exit code {process.returncode}.")
            print(f"❌ Error: Dependency installation failed. See output above for details.", file=sys.stderr)
            sys.exit(process.returncode)

    except FileNotFoundError:
        logger.exception(f"Error: Python interpreter '{sys.executable}' or script not found.")
        print(f"❌ Error: Could not find the Python interpreter or the installation script.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.exception(f"An unexpected error occurred during developer environment setup: {e}")
        print(f"❌ An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
