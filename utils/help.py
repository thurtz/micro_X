#!/usr/bin/env python

import argparse
import sys

# --- Help Text Definitions ---

# Using triple-quoted strings for easy multiline formatting.

GENERAL_HELP = """
micro_X AI-Enhanced Shell

A smart shell that translates natural language and streamlines your workflow.
Start by typing a command or use '/ai' to translate from English.

Common Commands:
  /ai <query>         - Translates natural language to a shell command.
  /help [topic]       - Displays this help message or help for a specific topic.
  /alias              - Manage command aliases (shortcuts).
  /command            - Manage command categorizations.
  /config             - Opens a web UI to manage your configuration.
  /snapshot           - Creates a snapshot of the project for context sharing.
  /tree               - Generates a file showing the project structure.
  /update             - Pulls the latest changes for micro_X.
  /list               - Lists available utility and user scripts.
  /ollama             - Manage the Ollama service.
  /dev                - Manage the multi-branch development environment.
    -> /dev --activate : Clones 'testing' and 'dev' branches to setup the dev environment.
  /setup_brew         - Installs Homebrew and required packages on macOS.

For more details on a specific feature, use '/help <topic>'.
Available Topics:
  ai, alias, command, config, dev, keybindings, security, utilities
"""

AI_HELP = """
micro_X Help: AI Features

The core of micro_X is its ability to translate natural language into shell commands.

/ai <query>
  - Translates your natural language <query> into a Linux command.
  - Example: /ai list all text files in the current folder
  - Example: /ai show me my IP address

AI Command Confirmation Flow:
  All AI-generated commands require your approval before execution. You will be prompted with the following options:
  [Y]es: Execute the command. Prompts for categorization if the command is new.
  [Ys/Ym/Yi]: Execute and categorize as 'simple', 'semi_interactive', or 'interactive_tui' in one step.
  [E]xplain: Ask the AI to explain what the command does before you decide.
  [M]odify: Load the command into the input field for you to edit.
  [C]ancel: Abort the command. It will not be executed.

AI Validation:
  If you type a command that micro_X has not seen before, it will first use an AI to determine if it's a valid command or a natural language phrase. If it seems like a phrase, it will be treated as if you had used '/ai'.
"""

ALIAS_HELP = """
micro_X Help: Command Aliases

Aliases are shortcuts for longer or more complex commands. You can use them to save typing and streamline your workflow.

Managing Aliases:
  micro_X uses the '/alias' command to manage your shortcuts.

  /alias --list              - Shows all currently active aliases (both default and user-defined).
  /alias --add /a "b"      - Creates a new user alias. E.g., /alias --add /snap "/utils generate_snapshot"
  /alias --remove /a         - Removes a user-defined alias.

Default vs. User Aliases:
  - Default aliases are built-in for convenience (e.g., /help, /command).
  - You can create your own in 'config/user_aliases.json' using the '/alias --add' command.
  - Your user aliases will always override any default alias with the same name.
"""

COMMAND_HELP = """
micro_X Help: Command Categorization

micro_X categorizes commands to execute them in the most appropriate way. When you run an unknown command, you will be prompted to choose a category.

Categories:
  - simple: For quick commands with direct text output (e.g., ls, pwd, echo).
  - semi_interactive: For commands that run longer or have a lot of output (e.g., apt update, ping). They run in a managed tmux window, with output shown upon completion.
  - interactive_tui: For full-screen, interactive applications (e.g., nano, vim, htop, ssh). They take over the screen in a tmux window until you exit.

/command <subcommand>
  - The '/command' utility (an alias for '/utils command') allows you to manage your saved categorizations.
  - Usage:
    /command list                    - Shows all categorized commands.
    /command add "<cmd>" <category>  - Adds or updates a command's category.
    /command remove "<cmd>"          - Removes a command from your user settings.
    /command move "<cmd>" <new_cat>  - Moves a command to a different category.
"""

UTILS_HELP = """
micro_X Help: Built-in Utilities

micro_X comes with several utility scripts to help manage the shell and your project.
While they can be run with '/utils <script_name>', it is recommended to use the shorter alias for them.

Common Utilities & Their Aliases:
  /alias
  /command
  /config
  /dev
  /snapshot
  /tree
  /list
  /ollama
  /update
  /test             (full command: /utils run_tests)

To see all available utility scripts, run '/list'.
"""

KEYS_HELP = """
micro_X Help: Keybindings

Keybindings for navigating the micro_X interface:

  Enter       - Submit the current command or query.
  Ctrl+C / D  - Exit micro_X or cancel an active interactive flow (like categorization or confirmation).
  Ctrl+N      - Insert a newline for multi-line commands.
  Up/Down     - Navigate through command history or move the cursor in a multi-line command.
  Tab         - Attempt command completion or insert 4 spaces.
  PageUp      - Scroll the main output area up.
  PageDown    - Scroll the main output area down.
"""

CONFIG_HELP = """
micro_X Help: Configuration

micro_X uses a hierarchical configuration system located in the 'config/' directory.

Configuration Files:
  - default_config.json: The base configuration. Do not edit this file directly, as updates will overwrite it. Use it as a reference.
  - user_config.json: Your personal configuration. Any setting you place here will override the default. This is where you should customize AI models, timeouts, etc.

  - default_command_categories.json: A pre-populated list of common command categories.
  - user_command_categories.json: Your personal command categorizations, managed via the '/command' utility.

  - default_aliases.json: Default aliases like /help, /snapshot, etc.
  - user_aliases.json: Your custom aliases, managed via the '/alias' utility.

Web-Based Configuration Manager:
  For an easy way to edit your user configuration files, run:
  /utils config_manager --start
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

DEV_HELP = """
micro_X Help: Developer & Contribution Guide

This guide is for users interested in contributing to micro_X or understanding its development workflow.

Branching Strategy & Integrity:
  - main: The most stable branch. Enforces strict integrity checks at startup.
  - testing: For release candidates. Also enforces strict integrity checks.
  - dev: The main development branch. Integrity checks are informational and do not block execution, allowing for local changes.

Setting up the Development Environment:
  - To set up the development environment, run this command from the 'main' branch:
    /dev --activate
  - This command will clone the 'testing' and 'dev' branches into subdirectories ('micro_X-testing/' and 'micro_X-dev/') and set up their environments.

Running Tests:
  - The project includes a comprehensive test suite.
  - To run tests for the current branch environment, use:
    /utils run_tests

Documentation:
  - For more in-depth developer documentation, please see the files in the 'docs/developer/' directory of the project.
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
        help="The topic to get help on. Available: ai, alias, command, utilities, keybindings, config, security, dev."
    )

    args, unknown = parser.parse_known_args()
    topic = args.topic.lower()

    if topic == 'general':
        print(GENERAL_HELP)
    elif topic == 'ai':
        print(AI_HELP)
    elif topic == 'alias':
        print(ALIAS_HELP)
    elif topic == 'command':
        print(COMMAND_HELP)
    elif topic == 'utils':
        print(UTILS_HELP)
    elif topic == 'keys':
        print(KEYS_HELP)
    elif topic == 'config':
        print(CONFIG_HELP)
    elif topic == 'security':
        print(SECURITY_HELP)
    elif topic == 'dev':
        print(DEV_HELP)
    else:
        print(f"Unknown help topic: '{args.topic}'")
        print("See '/help' for a list of available topics.")
        sys.exit(1)

if __name__ == "__main__":
    main()
