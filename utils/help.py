#!/usr/bin/env python

import argparse
import sys
import os

# --- Path Setup ---
# Add the utils directory to the Python path to allow importing from 'shared'
try:
    script_path = os.path.abspath(__file__)
    utils_dir = os.path.dirname(script_path)
    if utils_dir not in sys.path:
        sys.path.insert(0, utils_dir)
    from shared.help_utils import get_help_text_from_module
except ImportError as e:
    print(f"❌ Error: Could not import the shared module. Ensure this script is run from within the micro_X project structure.", file=sys.stderr)
    print(f"   Details: {e}", file=sys.stderr)
    sys.exit(1)

# --- Help Text Definitions ---

GENERAL_HELP = """
micro_X AI-Enhanced Shell

A smart shell that translates natural language and streamlines your workflow.
Start by typing a command or use '/translate' to translate from English.

Common Commands:
  /translate <query>  - Translates natural language to a shell command.
  /help [topic]       - Displays this help message or help for a specific topic.
  /alias              - Manage command aliases (shortcuts).
  /command            - Manage command categorizations.
  /config             - Opens a web UI to manage your configuration.
  /snapshot           - Creates a snapshot of the project for context sharing.
  /knowledge          - Manages and queries the local RAG knowledge base.
  /tree               - Generates a file showing the project structure.
  /docs               - Opens the project documentation in a web browser.
  /test               - Runs the project's test suite.
  /update             - Pulls the latest changes for micro_X.
  /list               - Lists available utility and user scripts.
  /ollama             - Manage the Ollama service.
  /dev                - Manage the multi-branch development environment.
    -> /dev --activate : Clones 'testing' and 'dev' branches to setup the dev environment.
  /setup_brew         - Installs Homebrew and required packages on macOS.
  /git_branch         - Displays the current git branch.


For more details on a specific feature, use '/help <topic>'.
Available Topics:
  translate, alias, command, config, dev, docs, git_branch, keybindings, knowledge, list, ollama, security, setup_brew, snapshot, test, tree, update, utilities
"""

AI_HELP = """
micro_X Help: AI Translation Features

The core of micro_X is its ability to translate natural language into shell commands.

/translate <query>
  - Translates your natural language <query> into a Linux command.
  - Example: /translate list all text files in the current folder
  - Example: /translate show me my IP address

AI Command Confirmation Flow:
  All AI-generated commands require your approval before execution. You will be prompted with the following options:
  [Y]es: Execute the command. Prompts for categorization if the command is new.
  [Ys/Ym/Yi]: Execute and categorize as 'simple', 'semi_interactive', or 'interactive_tui' in one step.
  [E]xplain: Ask the AI to explain what the command does before you decide.
  [M]odify: Load the command into the input field for you to edit.
  [C]ancel: Abort the command. It will not be executed.

AI Validation:
  If you type a command that micro_X has not seen before, it will first use an AI to determine if it's a valid command or a natural language phrase. If it seems like a phrase, it will be treated as if you had used '/translate'.
"""

KEYS_HELP = """
micro_X Help: Keybindings

Keybindings for navigating the micro_X interface:

  Enter       - Submit the current command or query.
  Ctrl+C / D  - Exit micro_X or cancel an active interactive flow (like categorization or confirmation).
  Ctrl+N      - Insert a newline for multi-line commands.
  Up/Down     - Navigate through command history or move the cursor in a multi-line command.
  Ctrl+Up/Down- Move cursor up/down in multi-line commands.
  Tab         - Attempt command completion or insert 4 spaces.
  PageUp      - Scroll the main output area up.
  PageDown    - Scroll the main output area down.

Tmux Window Management:
  micro_X runs inside a tmux session, allowing for multiple windows.

  Ctrl-b c    - Create a new window.
  Ctrl-b n    - Navigate to the next window.
  Ctrl-b p    - Navigate to the previous window.
  Ctrl-b &    - Close the current window (will prompt for confirmation).
"""

SECURITY_HELP = """
micro_X Help: Security Features

micro_X is designed with safety in mind, but user vigilance is key when executing AI-generated commands.

Multi-Layered Security:
  1. Deny-List: A list of dangerous command patterns (e.g., 'rm -rf /') is defined in the configuration. Commands matching these patterns are automatically blocked.
  2. Warn-List: A list of sensitive commands (e.g., 'fdisk', 'dd', 'visudo') triggers an extra "Are you sure?" confirmation prompt before execution, even if you typed them manually.
  3. User Confirmation: This is the primary safety feature. No AI-generated command is ever run without your explicit approval. Always use the [E]xplain, [M]odify, or [C]ancel options if you are unsure about a suggested command.

Your Responsibility:
  - Always review commands before execution.
  - AI can make mistakes. Do not blindly trust AI-generated commands, especially for system-critical operations.
  - The 'Explain' feature is your best tool for understanding a command's purpose and potential impact.
"""

UTILITIES_HELP = """
micro_X Help: Built-in Utilities

micro_X comes with several utility scripts to help manage the shell and your project.
While they can be run with '/utils <script_name>', it is recommended to use the shorter alias for them.

Common Utilities & Their Aliases:
  /alias              - Manage command aliases.
  /command            - Manage command categorizations.
  /config             - Opens a web UI to manage your configuration.
  /dev                - Manage the multi-branch development environment.
  /docs               - Opens the project documentation in a web browser.
  /git_branch         - Displays the current git branch.
  /knowledge          - Manages and queries the local RAG knowledge base.
  /list               - Lists available utility and user scripts.
  /ollama             - Manage the Ollama service.
  /setup_brew         - Installs Homebrew and required packages on macOS.
  /snapshot           - Creates a snapshot of the project for context sharing.
  /test               - Runs the project's test suite.
  /tree               - Generates a file showing the project structure.
  /update             - Pulls the latest changes for micro_X.

To see all available utility scripts, run '/list'.
For more details on a specific utility, use '/help <utility_name>'.
"""

# --- Main Logic ---

def main():
    """Parses arguments and displays the appropriate help text."""
    parser = argparse.ArgumentParser(
        description="Provides help for the micro_X shell and its features.",
        add_help=False # We are creating our own help system
    )
    parser.add_argument(
        'topic',
        nargs='?',
        default='general',
        help="The topic to get help on. Available: translate, alias, command, utilities, keybindings, config, security, dev."
    )

    args, unknown = parser.parse_known_args()
    topic = args.topic.lower()

    if topic == 'general':
        print(GENERAL_HELP)
    elif topic == 'translate':
        print(AI_HELP)
    elif topic == 'utilities':
        print(UTILITIES_HELP)
    elif topic in ('alias', 'command', 'config', 'dev', 'docs', 'git_branch', 'knowledge', 'list', 'ollama', 'setup_brew', 'snapshot', 'test', 'tree', 'update'):
        module_name = {
            'alias': 'alias.py',
            'command': 'command.py',
            'config': 'config_manager.py',
            'dev': 'dev.py',
            'docs': 'docs.py',
            'git_branch': 'git_branch.py',
            'knowledge': 'knowledge.py',
            'list': 'list_scripts.py',
            'ollama': 'ollama_cli.py',
            'setup_brew': 'setup_brew.py',
            'snapshot': 'generate_snapshot.py',
            'test': 'run_tests.py',
            'tree': 'generate_tree.py',
            'update': 'update.py'
        }[topic]
        utils_dir = os.path.dirname(os.path.abspath(__file__))
        module_path = os.path.join(utils_dir, module_name)
        help_text = get_help_text_from_module(module_path)
        if help_text:
            print(help_text)
        else:
            print(f"Could not retrieve help text for topic: '{topic}'")
            sys.exit(1)
    elif topic == 'keybindings':
        print(KEYS_HELP)
    elif topic == 'security':
        print(SECURITY_HELP)
    else:
        print(f"Unknown help topic: '{args.topic}'")
        print("See '/help' for a list of available topics.")
        sys.exit(1)

if __name__ == "__main__":
    main()