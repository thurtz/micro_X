
import os
import sys
import webbrowser
import argparse
import shutil
import subprocess

# --- Help Text ---
HELP_TEXT = """
micro_X Help: /docs Utility

This utility opens the local micro_X Sphinx documentation in your default web browser.

Usage:
  /docs             Opens documentation in the default graphical web browser.
  /docs --lynx      Opens documentation in the Lynx text-based browser.
  /docs --help      Shows this help message.

The script will look for the main index.html file in the 'docs/source/build/html' directory of the project. If the file is not found, it will print an error message.
"""

def main(args):
    """
    Finds and opens the local Sphinx documentation in a web browser.
    """
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
    class HelpAction(argparse.Action):
        def __init__(self, option_strings, dest, **kwargs):
            super(HelpAction, self).__init__(option_strings, dest, nargs=0, **kwargs)
        def __call__(self, parser, namespace, values, option_string=None):
            print(HELP_TEXT)
            parser.exit()

    parser = argparse.ArgumentParser(
        description="Finds and opens the local micro_X documentation in a web browser.",
        add_help=False
    )
    parser.add_argument('-h', '--help', action=HelpAction, help='show this help message and exit')
    parser.add_argument(
        '--lynx', 
        action='store_true', 
        help='Open documentation in the Lynx text-based browser.'
    )

    # If no arguments are provided, print help text
    if len(sys.argv) == 1:
        main(parser.parse_args())
    else:
        args = parser.parse_args()
        main(args)
