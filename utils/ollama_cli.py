#!/usr/bin/env python

import asyncio
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
    # Now we can safely import from modules
    from modules import ollama_manager
    from main import load_configuration_early # Import config loader from main
except ImportError as e:
    print(f"❌ Error: Could not import necessary modules. Ensure this script is run from within the micro_X project structure.", file=sys.stderr)
    print(f"   Details: {e}", file=sys.stderr)
    sys.exit(1)

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Help Text ---
HELP_TEXT = """
micro_X Help: /ollama Utility

This utility manages the Ollama service, which is used to run local AI models.

Usage:
  /ollama <subcommand>

Subcommands:
  start     - Starts the managed Ollama service if it's not already running.
  stop      - Stops the managed Ollama service.
  restart   - Restarts the managed Ollama service.
  status    - Shows the current status of the Ollama service.
  help      - Shows this help message.
"""

def print_for_manager(message, style_class='INFO'):
    """A simple print function to mimic the UI manager's append_output for this standalone script."""
    # Map style classes to simple prefixes for console output
    prefix_map = {
        'error': '❌ Error:',
        'success': '✅ Success:',
        'warning': '⚠️ Warning:',
        'info': 'ℹ️ Info:',
        'info-header': '---',
        'default': ''
    }
    prefix = prefix_map.get(style_class, 'ℹ️')
    print(f"{prefix} {message}")

async def main():
    """Main async function to parse arguments and execute ollama management commands."""
    # Load the main application configuration
    try:
        # We need to call the global function from main, not an instance method
        load_configuration_early()
        # The configuration is loaded into a global 'config' variable in main.py,
        # which we need to access.
        from main import config
    except Exception as e:
        print(f"❌ Error: Failed to load application configuration: {e}", file=sys.stderr)
        sys.exit(1)

    class HelpAction(argparse.Action):
        def __init__(self, option_strings, dest, **kwargs):
            super(HelpAction, self).__init__(option_strings, dest, nargs=0, **kwargs)
        def __call__(self, parser, namespace, values, option_string=None):
            print(HELP_TEXT)
            parser.exit()

    parser = argparse.ArgumentParser(
        description="Manage the Ollama service for the micro_X shell.",
        add_help=False
    )
    parser.add_argument('-h', '--help', action=HelpAction, help='show this help message and exit')
    parser.add_argument('subcommand', nargs='?', default='help', help='Available subcommands: start, stop, restart, status, help')

    args = parser.parse_args()

    # The ollama_manager functions now require the config and a callback.
    # We provide the loaded config and our simple print function.
    if args.subcommand == 'start':
        await ollama_manager.explicit_start_ollama_service(config, print_for_manager)
    elif args.subcommand == 'stop':
        await ollama_manager.explicit_stop_ollama_service(config, print_for_manager)
    elif args.subcommand == 'restart':
        await ollama_manager.explicit_restart_ollama_service(config, print_for_manager)
    elif args.subcommand == 'status':
        await ollama_manager.get_ollama_status_info(config, print_for_manager)
    elif args.subcommand == 'help':
        print(HELP_TEXT)


if __name__ == "__main__":
    # The main entry point for the script
    # asyncio.run() is a convenient way to run the top-level async main() function.
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"An unexpected error occurred in the ollama_cli utility: {e}", exc_info=True)
        print(f"❌ An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)