# **micro_X: The AI-Enhanced Shell**

micro_X is an intelligent, interactive shell environment designed to bridge the gap between natural language and executable Linux commands. It leverages local large language models (LLMs) via Ollama to translate your queries, validate commands, explain their functionality, and streamline your command-line workflow. It also features branch-aware integrity checks to ensure code reliability when running on stable or testing branches.
GitHub Repository: https://github.com/thurtz/micro_X.git
Detailed User Guide: docs/user_guide/index.md

## **Quick Start / Installation**

### **Step 1: General Setup**

It is recommended that all users start by cloning and setting up the main branch for the most stable experience.

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/thurtz/micro_X.git
    cd micro_X
    ```
2.  **Make the Setup Script Executable:**
    ```bash
    chmod +x setup.sh
    ```
3.  **Run the Unified Setup Script:**
    ```bash
    ./setup.sh
    ```
    *   The script will guide you through installing dependencies, setting up the Python environment, and pulling the necessary Ollama models. Follow the on-screen prompts.

### **Step 2 (Optional): For Developers and Testers**

If you wish to contribute to development or test new features, you can activate the development environment from your stable main branch installation.

1.  **Launch micro_X from your main branch installation:**
    ```bash
    ./micro_X.sh
    ```
2.  **Run the Activation Utility:** Inside micro_X, run the following command:
    ```bash
    /dev --activate
    ```
    *   This command will clone the testing and dev branches into new subdirectories (micro_X-testing/ and micro_X-dev/) and run the setup process for each of them.
    *   You will then have three separate, managed installations of micro_X.

## **Overview**

micro_X provides a text-based user interface (TUI) where you can:

*   Type standard Linux commands.
*   Force natural language queries (prefixed with /ai) to have them translated into shell commands.
*   Benefit from AI-powered validation and translation of natural language (without the need for /ai prefixed) or directly entered commands.
*   **Confirm AI-Generated Commands:** Review, get explanations, modify, or cancel commands suggested by the AI before execution.
*   Categorize commands (simple, semi_interactive, interactive_tui) for appropriate execution, including running interactive commands in tmux.
*   **Run Custom Scripts:** Add your own Python scripts to a dedicated `user_scripts/` directory and run them with the `/run` command.
*   **Create Command Aliases:** Use the built-in alias utility to create shortcuts for your favorite or frequently used commands.
*   Manage command history and categorizations.
*   Control the underlying Ollama service directly from within the shell.
*   **Branch-Aware Integrity & Developer Mode:** Automatically enables a permissive 'Developer Mode' when running off the dev branch. Performs startup integrity checks on main and testing branches.
*   **Web-Based Configuration Manager:** An integrated tool to easily view and edit user configurations and command categorizations via a web interface (launched with the **/config** command).

## **Key Features**

*   **AI-Powered Command Generation & Validation:**
    *   **Natural Language to Command Translation:** Uses configurable Ollama models for initial translation.
    *   **AI-Powered Command Validation:** Employs a configurable Ollama model to assess command validity.
    *   **AI-Powered Command Explanation:** Request an explanation for AI-generated commands to understand their purpose and potential impact.
    *   **Interactive Command Confirmation:** For AI-generated commands, micro_X prompts for user action:
        *   `[Y]es`: Execute the command (will prompt for categorization if new).
        *   `[Ys] Simple & Run`: Execute and categorize as 'simple'.
        *   `[Ym] Semi-Interactive & Run`: Execute and categorize as 'semi_interactive'.
        *   `[Yi] TUI & Run`: Execute and categorize as 'interactive_tui'.
        *   `[E]xplain`: Ask AI to explain before deciding.
        *   `[M]odify`: Load command into input field for editing.
        *   `[C]ancel`: Do not execute.

*   **Command Categorization & Execution:**
    *   `simple`: Direct execution, output captured in micro_X.
    *   `semi_interactive`: Runs in a new tmux window. Output typically captured after completion.
    *   `interactive_tui`: Runs fully interactively in a new tmux window.
    *   Users manage categories via the `/command` alias.

*   **Ollama Service Management:** Control the Ollama service directly from micro_X using the `/ollama` command (subcommands: `start`, `stop`, `restart`, `status`, `help`).

*   **Runtime AI Configuration:** View and modify AI model settings (e.g., model name, temperature) at runtime using the `/config` command. Save changes to your user configuration file.

*   **Branch-Aware Integrity & Developer Mode:**
    *   **Developer Mode:** Activated on the `dev` branch or if integrity checks cannot be performed. Integrity checks are informational, allowing development without interruption.
    *   **Protected Mode:** Active on `main` or `testing` branches. Performs strict startup integrity checks (clean working directory, sync with remote). Failure halts execution to prevent running unstable code.

*   **Multi-Layered Security:**
    *   Configurable **deny-list** in `config/default_config.json` blocks dangerous command patterns.
    *   **Warn-list** triggers extra confirmation for sensitive commands.
    *   Primary defense: interactive **user confirmation flow** for all AI-generated commands.

*   **Shell-like Functionality:** Supports `cd`, history, and shell variable expansion.

*   **Logging & Configuration:** Detailed logging and persistent configuration.

*   **Web-Based Configuration Manager:** Launch with the `/config` command to easily manage `user_config.json` and `user_command_categories.json` via a web UI.

## **Usage**

1.  **Ensure Ollama is Running** (use `/ollama status` within micro_X or check externally).
2.  **Launch micro_X:**
    *   From your `micro_X` (main) directory, run: `./micro_X.sh`
    *   To run the dev version, navigate to its directory and run its launch script: `cd micro_X-dev && ./micro_X.sh`

### **Operational Modes (Based on Git Branch)**

micro_X's behavior at startup is influenced by the current Git branch:

*   **Developer Mode:** Automatically active if you are on the `dev` branch. In this mode, startup integrity checks are informational and do not halt execution, allowing for local code changes.
*   **Protected Mode:** Active if you are on the `main` or `testing` branches. micro_X performs strict integrity checks to ensure the code is clean and synced with the remote repository. If these checks fail, the application will halt to prevent running on potentially unstable code.

### **Interacting with micro_X**

*   **Direct Commands:** Type any Linux command and press Enter (e.g., `ls -l`).
*   **AI Translation (`/ai`):** Prefix your query with `/ai` to translate it into a command.
    *   `(/~) > /ai list text files`
*   **User Scripts (`/run`):** Execute your own scripts from the `user_scripts/` directory.
    *   `(/~) > /run my_script --with-args`
*   **Aliases (`/alias`, `/command`, `/config`, etc.):** Use aliases for common utilities.
    *   `(/~) > /alias --add /snap /snapshot`
    *   `(/~) > /config --start`
*   **Help (`/help`):** Displays the main help message.
*   **Exit (`/exit` or `exit`):** Exits the micro_X shell.

## **Troubleshooting**

*   **Integrity Check Failed:** If micro_X halts on startup on the `main` or `testing` branch, it means your local code has uncommitted changes or is not synced with the official repository.
    *   **Solution:** Open a standard terminal in the project directory. Use `git status` to see the changes. You can either discard them (`git reset --hard origin/main`) or commit them on a separate feature branch. For development, it's best to switch to the `dev` branch (`git checkout dev`).

## **Future Ideas & Contributions**

*   More sophisticated security sandboxing options.
*   Plugin system for extending functionality.
*   GPG signature verification for commits/tags on the main branch as part of integrity checks.

Contributions, bug reports, and feature requests are welcome! Please open an issue or pull request on the GitHub repository.
This README was drafted with the assistance of an AI and subsequently updated based on project evolution.