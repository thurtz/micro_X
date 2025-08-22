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
    from main import load_configuration # Import config loader from main
except ImportError as e:
    print(f"❌ Error: Could not import necessary modules. Ensure this script is run from within the micro_X project structure.", file=sys.stderr)
    print(f"   Details: {e}", file=sys.stderr)
    sys.exit(1)

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
        load_configuration()
        # The configuration is loaded into a global 'config' variable in main.py,
        # which we need to access.
        from main import config
    except Exception as e:
        print(f"❌ Error: Failed to load application configuration: {e}", file=sys.stderr)
        sys.exit(1)


    parser = argparse.ArgumentParser(
        description="Manage the Ollama service for the micro_X shell.",
        epilog="This utility interacts with the Ollama service, potentially using tmux for management."
    )
    # Use a subparsers approach for clearer command structure
    subparsers = parser.add_subparsers(dest='subcommand', help='Available subcommands', required=True)

    subparsers.add_parser('start', help="Start the managed Ollama service if it's not running.")
    subparsers.add_parser('stop', help="Stop the managed Ollama service.")
    subparsers.add_parser('restart', help="Restart the managed Ollama service.")
    subparsers.add_parser('status', help="Show the current status of the Ollama service.")
    subparsers.add_parser('help', help="Show this help message.")

    # In a real scenario, sys.argv would be used. For direct calls, you might pass args.
    # When run from shell_engine, the arguments after 'ollama_cli.py' are parsed.
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
        parser.print_help()


if __name__ == "__main__":
    # The main entry point for the script
    # asyncio.run() is a convenient way to run the top-level async main() function.
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"An unexpected error occurred in the ollama_cli utility: {e}", exc_info=True)
        print(f"❌ An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
