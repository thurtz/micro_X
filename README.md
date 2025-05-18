# micro_X: The AI-Enhanced Shell

**micro_X** is an intelligent, interactive shell environment designed to bridge the gap between natural language and executable Linux commands. It leverages local large language models (LLMs) via Ollama to translate your queries, validate commands, explain their functionality, and streamline your command-line workflow.

GitHub Repository: [https://github.com/thurtz/micro_X.git](https://github.com/thurtz/micro_X.git)  
Detailed User Guide: `docs/micro_X_User_Guide.md`

## Overview

micro_X provides a text-based user interface (TUI) where you can:

* Type standard Linux commands.
* Enter natural language queries (prefixed with `/ai`) to have them translated into shell commands.
* Benefit from AI-powered validation of translated or directly entered commands.
* **Confirm AI-Generated Commands:** Review, get explanations, modify, or cancel commands suggested by the AI before execution.
* Categorize commands (`simple`, `semi_interactive`, `interactive_tui`) for appropriate execution, including running interactive commands in tmux.
* Manage command history and categorizations.
* Control the underlying Ollama service directly from within the shell.

## Key Features

* **Natural Language to Command Translation:** Uses a configurable "primary_translator" Ollama model for initial translation (default example: `llama3.2:3b`).
* **Optional Secondary Direct Translator:** Can leverage a configurable "direct_translator" model specialized in direct command output (default example: `vitali87/shell-commands-qwen2-1.5b`) as a fallback or alternative.
* **AI-Powered Command Validation:** Employs a configurable "validator" Ollama model (default example: `herawen/lisa:latest`) to assess command validity.
* **AI-Powered Command Explanation:** Before executing an AI-generated command, you can request an explanation from a configurable "explainer" Ollama model (default example: `llama3.2:3b`) to understand its purpose and potential impact.
* **Interactive Command Confirmation:** For AI-generated commands, micro_X prompts for user action:
  * `[Y]es`: Execute the command (will prompt for categorization if the command is new).
  * `[Ys]` Simple & Run: Execute and categorize the command as 'simple'.
  * `[Ym]` Semi-Interactive & Run: Execute and categorize the command as 'semi_interactive'.
  * `[Yi]` TUI & Run: Execute and categorize the command as 'interactive_tui'.
  * `[E]xplain`: Ask the AI to explain the command before deciding.
  * `[M]odify`: Load the command into the input field for editing.
  * `[C]ancel`: Do not execute the command.
* **Command Categorization & Execution:**
  * `simple`: Direct execution, output captured in micro_X.
  * `semi_interactive`: Runs in a new tmux window. Output is typically captured after completion.
    * **Smart Output Handling:** If a `semi_interactive` command produces output resembling a full-screen TUI application, micro_X avoids displaying garbled output and suggests re-categorizing to `interactive_tui`.
  * `interactive_tui`: Runs fully interactively in a new tmux window.
  * Users manage categories via `/command` subcommands.
* **Ollama Service Management (`/ollama` command):**
  * Control the Ollama service directly from micro_X.
  * Subcommands: `start`, `stop`, `restart`, `status`, `help`.
* **Modular Architecture:**
  * `modules/ai_handler.py`: Manages all interactions with Ollama LLMs.
  * `modules/category_manager.py`: Handles command categories.
  * `modules/output_analyzer.py`: Detects TUI-like output.
  * `modules/ollama_manager.py`: Manages the Ollama service lifecycle.
* **Shell-like Functionality:** Supports `cd`, `history`, and shell variable expansion.
* **Security:** Basic sanitization for potentially dangerous commands. The command confirmation flow with the "Explain" option is a key safety feature. **Always review and understand commands, especially AI-generated ones, before execution.**
* **Logging & Configuration:** Detailed logging and persistent configuration.

## Supported Platforms & Setup

micro_X is designed to be adaptable and has specific setup guidance for the following environments:

* **Linux Mint (and compatible Debian-based systems):**
  * Automated setup script: `setup_micro_x_mint.sh`
  * Detailed instructions: [setup_micro_x_mint.md](https://github.com/thurtz/micro_X/blob/main/setup_micro_x_mint.md)
* **macOS:**
  * Automated setup script: `setup_micro_x_mac.sh`
  * Detailed instructions: [setup_micro_x_mac.md](https://github.com/thurtz/micro_X/blob/main/setup_micro_x_mac.md)
* **Termux (Android):**
  * Setup script: `setup_micro_x_termux.sh`
  * Detailed instructions: [setup_micro_x_termux.md](https://github.com/thurtz/micro_X/blob/main/setup_micro_x_termux.md)
* **WSL (Windows Subsystem for Linux):**
  * Setup script: `setup_micro_x_wsl.sh`
  * Detailed instructions: [setup_micro_x_wsl.md](https://github.com/thurtz/micro_X/blob/main/setup_micro_x_wsl.md)

**General Prerequisites (Common across platforms, details in specific setup guides):**

* Python 3.8+
* `pip3` & `python3-venv`
* `tmux` (Required for `semi_interactive` and `interactive_tui` commands)
* Ollama ([ollama.com](https://ollama.com/)) installed and running.
* **Required Ollama Models (Examples - these are configurable):**
  * Pull via `ollama pull <model_name>` (e.g., `ollama pull llama3.2:3b`)
  * Primary Translator (e.g., `llama3.2:3b`)
  * Direct Translator (e.g., `vitali87/shell-commands-qwen2-1.5b`)
  * Validator (e.g., `herawen/lisa:latest`)
  * Explainer (e.g., `llama3.2:3b`)

**General Setup Steps (Refer to specific platform .md files for details):**

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/thurtz/micro_X.git
    cd micro_X
    ```
2.  Navigate to the `micro_X` directory.
3.  Make the appropriate setup script executable (e.g., `chmod +x setup_micro_x_mint.sh`).
4.  Run the Setup Script (e.g., `./setup_micro_x_mint.sh`).
    These scripts typically handle dependencies, Python environment setup, and Ollama model guidance.

## Usage

1.  **Ensure Ollama is Running** (use `/ollama status` within micro_X or check externally).
2.  **Launch micro_X:**
    * **Desktop Menu:** If installed (Linux Mint), look for "micro_X".
    * **Using the Launch Script (Recommended):** From the `micro_X` directory:
        ```bash
        ./micro_X.sh
        ```
    * **Manually:**
        ```bash
        source .venv/bin/activate
        python3 main.py
        ```

### Interacting with micro_X

* **Direct Commands:** Type any Linux command and press Enter (e.g., `ls -l`).
* **AI Translation (`/ai`):** Prefix your query with `/ai`.
    ```
    (~) > /ai list all python files in my documents folder
    ```
    If the AI suggests a command, you'll be prompted to confirm, explain, modify, or cancel it.
* **Command Management (`/command`):** Use `/command help` for options to add, remove, list, or move categorized commands.
    ```
    (~) > /command list
    (~) > /command add "my_custom_script.sh --interactive" interactive_tui
    ```
* **Ollama Management (`/ollama`):** Control the Ollama service.
    ```
    (~) > /ollama status
    (~) > /ollama start
    (~) > /ollama help
    ```
* **Utilities (`/utils`):** Run scripts from the `utils` directory.
    ```
    (~) > /utils list
    (~) > /utils generate_tree
    ```
* **Update (`/update`):** Check for and pull updates for micro_X.
* **Help (`/help`):** Displays the main help message.
* **Navigation & Control:**
    * `Ctrl+C` / `Ctrl+D`: Exit micro_X or cancel current categorization/confirmation.
    * `Enter`: Submit command/query.
    * `Up/Down Arrows`: Navigate command history / input lines.
    * `Tab`: Attempt completion / indent.
    * `PgUp/PgDn`: Scroll output area.

## Configuration

micro_X uses a hierarchical configuration system (fallback -> default -> user):

* **Default Configuration:** `config/default_config.json` (AI models, prompts, timeouts, behavior).
* **User Configuration:** `config/user_config.json` (Your overrides).
* **Default Command Categories:** `config/default_command_categories.json`.
* **User Command Categories:** `config/user_command_categories.json` (Your categorizations).
* **Command History:** `.micro_x_history` (project root).
* **Logs:** `logs/micro_x.log`.
* **Tmux Configuration:** `config/.tmux.conf` (used by `micro_X.sh`).

## Security Considerations

* **AI-Generated Commands:** While micro_X includes AI validation and a basic command sanitizer, **AI can still generate unexpected or harmful commands.**
* **Review and Understand:** Always use the `[E]xplain` option in the confirmation flow for AI-generated commands if you are unsure about their function. Modify or cancel commands if they seem suspicious.
* **User Responsibility:** You are responsible for the commands executed in your environment.

## Future Ideas & Contributions

* Enhanced parsing for AI output.
* More sophisticated security sandboxing options.
* User-configurable AI parameters (temperature, etc.) directly via commands.
* Plugin system for extending functionality.

Contributions, bug reports, and feature requests are welcome! Please open an issue or pull request on the [GitHub repository](https://github.com/thurtz/micro_X.git).

*This README was drafted with the assistance of an AI and subsequently updated based on project evolution.*
