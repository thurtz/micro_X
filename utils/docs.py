
import os
import sys
import webbrowser
import argparse
import shutil
import subprocess
import asyncio
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.query_engine import query_knowledge_base, query_knowledge_base_rag
from utils.shared.api_client import get_input

# --- Help Text ---
HELP_TEXT = """
micro_X Help: /docs Utility

This utility opens the local micro_X Sphinx documentation or allows you to query it.

Usage:
  /docs                       Opens documentation in the default graphical web browser.
  /docs --query <question>    Queries the documentation knowledge base.
  /docs --query <question> --rag Queries the documentation with a language model for a natural language response.
  /docs --lynx                Opens documentation in the Lynx text-based browser.
  /docs --help                Shows this help message.

The script will look for the main index.html file in the 'docs/source/build/html' directory of the project. If the file is not found, it will print an error message.
"""

def main():
    """
    Finds and opens the local Sphinx documentation in a web browser or queries the knowledge base.
    """
    parser = argparse.ArgumentParser(
        description="Finds and opens the local micro_X documentation in a web browser.",
        add_help=False
    )
    parser.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help='show this help message and exit')
    parser.add_argument(
        '--lynx', 
        action='store_true', 
        help='Open documentation in the Lynx text-based browser.'
    )
    parser.add_argument(
        '--query', 
        nargs='+',
        type=str,
        help='Query the documentation knowledge base.'
    )
    parser.add_argument(
        '--rag', 
        action='store_true', 
        help='Use a language model to generate a natural language response.'
    )

    args = parser.parse_args()

    # --- Logging Configuration ---
    if not logging.getLogger().hasHandlers():
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'micro_x.log')
        log_level = logging.INFO
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(log_level)

    if args.query:
        # --- Check if Knowledge Base is Built ---
        # We need to import the necessary modules here, inside the 'if' block,
        # to avoid loading them when just opening the browser.
        from modules import config_handler
        from modules.rag_manager import RAGManager

        # A minimal config load is needed for the RAGManager
        project_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir = os.path.join(project_root_dir, 'config')
        default_config_path = os.path.join(config_dir, 'default_config.json')
        user_config_path = os.path.join(config_dir, 'user_config.json')
        
        config = config_handler.load_jsonc_file(default_config_path) or {}
        user_settings = config_handler.load_jsonc_file(user_config_path)
        if user_settings:
            # A simple merge for this check
            config.update(user_settings)

        rag_manager = RAGManager(config, name='micro_X_docs')
        rag_manager.initialize()

        if rag_manager.vector_store and rag_manager.vector_store._collection.count() == 0:
            print("⚠️  The 'micro_X_docs' knowledge base is empty or has not been built yet.")
            choice = get_input("Would you like to build it now? This process may take around 20 minutes. [y/N]: ").strip().lower()
            
            if choice == 'y':
                print("\n🚀 Starting build process...")
                knowledge_script = os.path.join(os.path.dirname(__file__), 'knowledge.py')
                docs_source = os.path.join(project_root_dir, 'docs', 'source')
                
                try:
                    subprocess.run(
                        [sys.executable, knowledge_script, '--name', 'micro_X_docs', 'add-dir', docs_source],
                        check=True
                    )
                    print("\n✅ Knowledge base built successfully! Retrying query...")
                    # Re-initialize to ensure fresh state
                    rag_manager = RAGManager(config, name='micro_X_docs')
                    rag_manager.initialize()
                except subprocess.CalledProcessError as e:
                    print(f"\n❌ Error building knowledge base: {e}")
                    sys.exit(1)
            else:
                print("\nTo enable documentation queries later, please run:")
                print("    /knowledge --name micro_X_docs add-dir docs/source\n")
                sys.exit(0)

        # --- Proceed with Query ---
        query_text = " ".join(args.query)
        if args.rag:
            response = asyncio.run(query_knowledge_base_rag(kb_name="micro_X_docs", query=query_text))
        else:
            response = query_knowledge_base(kb_name="micro_X_docs", query=query_text)
        print("\nResponse:")
        print(response)
        sys.exit(0)

    try:
        # The script is in /utils, so the project root is one level up.
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        docs_index_path = os.path.join(project_root, 'docs', 'source', 'build', 'html', 'index.html')

        if not os.path.isfile(docs_index_path):
            print("❌ Error: Documentation file not found.", file=sys.stderr)
            print(f"   Expected path: {docs_index_path}", file=sys.stderr)
            print("   Please ensure the documentation has been built and is present.", file=sys.stderr)
            sys.exit(1)

        if args.lynx:
            if shutil.which('lynx'):
                print("Attempting to open documentation in lynx...")
                # Using subprocess.run to launch lynx in the foreground
                subprocess.run(['lynx', docs_index_path])
            else:
                print("❌ Error: --lynx option used, but 'lynx' command not found.", file=sys.stderr)
                print("   Please install lynx to use this feature.", file=sys.stderr)
                sys.exit(1)
        else:
            # Use file:// URI scheme to ensure it opens as a local file
            docs_uri = f"file://{os.path.realpath(docs_index_path)}"
            print(f"Attempting to open documentation at: {docs_uri}")
            webbrowser.open(docs_uri)
            print("✅ Documentation should now be open in your default web browser.")
            
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
