# utils/knowledge.py
import argparse
import asyncio
import logging
import os
import re
import sys

# Add project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.rag_manager import RAGManager
from modules import config_handler
from modules.query_engine import query_knowledge_base, query_knowledge_base_rag

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def merge_configs(base, override):
    """ Helper function to recursively merge dictionaries. """
    merged = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged

def load_config():
    """Loads the main application configuration."""
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    CONFIG_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'config')
    DEFAULT_CONFIG_FILENAME = "default_config.json"
    USER_CONFIG_FILENAME = "user_config.json"

    default_config_path = os.path.join(CONFIG_DIR, DEFAULT_CONFIG_FILENAME)
    user_config_path = os.path.join(CONFIG_DIR, USER_CONFIG_FILENAME)

    config = config_handler.load_jsonc_file(default_config_path)
    if config is None:
        logger.error("CRITICAL: Default configuration not found. Exiting.")
        sys.exit(1)

    user_settings = config_handler.load_jsonc_file(user_config_path)
    if user_settings:
        config = merge_configs(config, user_settings)

    return config

# --- Help Text ---
HELP_TEXT = """
micro_X Knowledge Base Utility

Usage: /knowledge [--name <kb_name>] <command> [options] [-q]

Options:
  --name <kb_name>    Specify the knowledge base to use (defaults to 'default').
  --rag               Use a language model to generate a natural language response to a query.

Commands:
  query <text>        Ask a question to the knowledge base.
  add-file <path>     Add a local file to the knowledge base. Path must be absolute.
  add-dir <path>      Recursively add all supported files in a local directory. Path must be absolute.
  add-url <url> [--recursive] [--save-cache] [--depth N]      Add content from a URL to the knowledge base.

Description:
  This utility manages a local vector knowledge base for Retrieval-Augmented Generation (RAG).
  You can add documents from local files, directories, or web pages. Once added, you can
  query the knowledge base using natural language.
"""

# --- Main Execution --- 
async def main():
    class HelpAction(argparse.Action):
        def __init__(self, option_strings, dest, **kwargs):
            super(HelpAction, self).__init__(option_strings, dest, nargs=0, **kwargs)
        def __call__(self, parser, namespace, values, option_string=None):
            print(HELP_TEXT)
            parser.exit()

    # --- Two-Pass Parser Setup ---
    # This allows global flags like --name to be used before or after the command.

    # 1. Define a parser for global arguments
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument('-q', '--quiet', action='store_true', help='Suppress informational output.')
    global_parser.add_argument('--name', type=str, default='default', help='Specify the name of the knowledge base to use.')
    global_parser.add_argument('--rag', action='store_true', help='Use a language model to generate a natural language response.')
    
    # 2. Parse the known global args, and leave the rest for the command parser
    global_args, remaining_argv = global_parser.parse_known_args()

    # 3. Define the main parser and subparsers for commands
    parser = argparse.ArgumentParser(
        description="Manage and query the micro_X knowledge base.",
        add_help=False
    )
    parser.add_argument('-h', '--help', action=HelpAction, help='show this help message and exit')
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: add-file
    parser_add_file = subparsers.add_parser("add-file", help="Add a single file to the knowledge base.")
    parser_add_file.add_argument("path", type=str, help="The absolute path to the file.")

    # Command: add-dir
    parser_add_dir = subparsers.add_parser("add-dir", help="Add all files in a directory to the knowledge base.")
    parser_add_dir.add_argument("path", type=str, help="The absolute path to the directory.")

    # Command: add-url
    parser_add_url = subparsers.add_parser("add-url", help="Add a URL to the knowledge base.")
    parser_add_url.add_argument("url", type=str, help="The URL to process.")
    parser_add_url.add_argument("--recursive", action="store_true", help="Enable recursive crawling of links (depth: 2).")
    parser_add_url.add_argument("--save-cache", action="store_true", help="Save the raw HTML content of crawled pages to a cache directory.")
    parser_add_url.add_argument("--depth", type=int, default=2, help="Set the maximum depth for recursive crawling. Default is 2.")

    # Command: query
    parser_query = subparsers.add_parser("query", help="Query the knowledge base.")
    parser_query.add_argument("query_text", type=str, nargs=argparse.REMAINDER, help="The question to ask.")

    # 4. Check if a command was provided. If not, print help.
    if not remaining_argv or remaining_argv[0] not in subparsers.choices.keys():
        # Also handle the case where only -h is passed after global args
        if not remaining_argv or remaining_argv == ['--help'] or remaining_argv == ['-h']:
             print(HELP_TEXT)
             sys.exit(0)

    # 5. Parse the remaining args for the command, merging them into the global_args namespace
    args = parser.parse_args(remaining_argv, namespace=global_args)

    # --- Logging Configuration ---
    if not logging.getLogger().hasHandlers():
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'micro_x.log')
        log_level = logging.WARNING if args.quiet else logging.INFO
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(log_level)

    # --- Initialization ---
    config = load_config()
    rag_manager = RAGManager(config, name=args.name)
    rag_manager.initialize()

    # --- Command Handling ---
    if args.command == "add-file":
        absolute_path = os.path.abspath(args.path)
        if os.path.isfile(absolute_path):
            rag_manager.add_file(absolute_path)
        else:
            logger.error(f"File not found at resolved path: '{absolute_path}'")

    elif args.command == "add-dir":
        absolute_path = os.path.abspath(args.path)
        if os.path.isdir(absolute_path):
            rag_manager.add_directory(absolute_path)
        else:
            logger.error(f"Directory not found at resolved path: '{absolute_path}'")

    elif args.command == "add-url":
        rag_manager.add_url(args.url, recursive=args.recursive, save_cache=args.save_cache, depth=args.depth)

    elif args.command == "query":
        query_text = " ".join(args.query_text)
        if args.rag:
            response = await query_knowledge_base_rag(kb_name=args.name, query=query_text)
        else:
            response = query_knowledge_base(kb_name=args.name, query=query_text)
        print("\nResponse:")
        print(response)

if __name__ == "__main__":
    asyncio.run(main())
