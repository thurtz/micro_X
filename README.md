# **micro\_X: The AI-Enhanced Shell**

**micro\_X** is an intelligent, interactive shell environment designed to bridge the gap between natural language and executable Linux commands. It leverages local large language models (LLMs) via Ollama to translate your queries, validate commands, and streamline your command-line workflow.

**GitHub Repository:** [https://github.com/thurtz/micro\_X.git](https://github.com/thurtz/micro_X.git)

## **Overview**

micro\_X provides a text-based user interface (TUI) where you can:

* Type standard Linux commands.
* Enter natural language queries (prefixed with `/ai`) to have them translated into shell commands.
* Benefit from AI-powered validation of translated or directly entered commands.
* Categorize commands (`simple`, `semi_interactive`, `interactive_tui`) for appropriate execution, including running interactive commands in `tmux`.
* Manage command history and categorizations.

## **Key Features**

* **Natural Language to Command Translation:** Uses a configurable "primary\_translator" Ollama model for initial translation (default example: `llama3.2:3b`).
* **Optional Secondary Direct Translator:** Can leverage a configurable "direct\_translator" model specialized in direct command output (default example: `vitali87/shell-commands-qwen2-1.5b`) as a fallback or alternative.
* **AI-Powered Command Validation:** Employs a configurable "validator" Ollama model (default example: `herawen/lisa:latest`) to assess command validity.
* **Command Categorization & Execution:**
    * `simple`: Direct execution, output captured in micro\_X.
    * `semi_interactive`: Runs in a new `tmux` window. Output is typically captured after completion.
        * **Smart Output Handling:** If a `semi_interactive` command produces output resembling a full-screen TUI application (e.g., many terminal control codes), micro\_X will avoid displaying the raw (often garbled) output. Instead, it provides a notification and suggests re-categorizing the command to `interactive_tui`.
    * `interactive_tui`: Runs fully interactively in a new `tmux` window. No output is captured back into micro\_X.
    * Users can manage these categories via `/command` subcommands.
* **Modular Architecture:**
    * `modules/ai_handler.py`: Manages all interactions with Ollama LLMs for translation and validation.
    * `modules/category_manager.py`: Handles the loading, merging, and modification of command categories.
    * `modules/output_analyzer.py`: Contains logic to detect TUI-like output (e.g., high density of ANSI escape codes) from `semi_interactive` commands.
* **Chained Command Support:** Capable of processing and executing commands linked by `&&`, `||`, `|`, etc.
* **Interactive TUI:** Built with `prompt_toolkit` for a user-friendly experience.
* **Shell-like Functionality:** Supports `cd`, history, and shell variable expansion.
* **Security:** Basic sanitization for potentially dangerous commands. **Note:** Executing AI-generated commands carries inherent risks. Always review commands before execution if unsure.
* **Logging & Configuration:** Detailed logging and persistent configuration for AI settings, command categories, and history.

## **Supported Platforms & Setup**

micro\_X is designed to be adaptable and has specific setup guidance for the following environments:

* **Linux Mint (and compatible Debian-based systems):**
    * Automated setup script: `setup.sh` (or `setup_micro_x_mint.sh`)
    * Detailed instructions: [setup\_micro\_x\_mint.md](https://github.com/thurtz/micro_X/blob/main/setup_micro_x_mint.md)
* **macOS:**
    * Automated setup script: `setup_micro_x_mac.sh`
    * Detailed instructions: [setup\_micro\_x\_mac.md](https://github.com/thurtz/micro_X/blob/main/setup_micro_x_mac.md)
* **Termux (Android):**
    * Setup script (guides through Termux-specific steps): `setup_micro_x_termux.sh`
    * Detailed instructions: [setup\_micro\_x_termux.md](https://github.com/thurtz/micro_X/blob/main/setup_micro_x_termux.md)
* **WSL (Windows Subsystem for Linux):**
    * Setup script (for within WSL, assumes Ollama on Windows host): `setup_micro_x_wsl.sh`
    * Detailed instructions: [setup\_micro_x_wsl.md](https://github.com/thurtz/micro_X/blob/main/setup_micro_x_wsl.md)

**General Prerequisites (Common across platforms, details in specific setup guides):**

* Python 3.8+
* `pip3` & `python3-venv`
* `tmux` (Required for `semi_interactive` and `interactive_tui` commands)
* Ollama ([ollama.com](https://ollama.com/)) installed and running.
* **Required Ollama Models (Examples - these are configurable, see Configuration section):**
    * Pull via `ollama pull <model_name>`
    * Primary Translator (e.g., `llama3.2:3b` - for `ai_models.primary_translator` in config)
    * Direct Translator (e.g., `vitali87/shell-commands-qwen2-1.5b` - for `ai_models.direct_translator` in config)
    * Validator (e.g., `herawen/lisa:latest` - for `ai_models.validator` in config)

**General Setup Steps (Refer to specific platform `.md` files for details):**

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/thurtz/micro_X.git](https://github.com/thurtz/micro_X.git)
    cd micro_X
    ```
2.  Navigate to the `micro_X` directory.
3.  Make the appropriate setup script executable:
    * For example, for Linux Mint:
        ```bash
        chmod +x setup_micro_x_mint.sh
        ```
    *(Use `setup_micro_x_mac.sh` for macOS, `setup_micro_x_termux.sh` for Termux, or `setup_micro_x_wsl.sh` for WSL).*
4.  Run the Setup Script:
    * For example:
        ```bash
        ./setup_micro_x_mint.sh
        ```
    These scripts typically:
    * Check and help install system dependencies.
    * Guide Ollama setup and model pulling.
    * Create a Python virtual environment (`.venv`).
    * Install Python packages from `requirements.txt`.
    * Make other necessary scripts executable.
    * Handle platform-specific configurations (like `.desktop` files or aliases).

## **Usage**

1.  **Ensure Ollama is Running** (on your host machine or as per your platform's setup).
2.  **Launch micro\_X:**
    * **Desktop Menu:** If a `.desktop` entry was installed (Linux Mint), look for "micro\_X".
    * **Using the Launch Script (Recommended for Terminal):**
        From within the `micro_X` directory:
        ```bash
        ./micro_X.sh
        ```
        *(This script also utilizes `config/.tmux.conf` to manage the micro_X session within `tmux`.)*
    * **Manually (from the `micro_X` directory):**
        ```bash
        source .venv/bin/activate
        python3 main.py
        ```
    * **macOS Alias:** If you set up an alias (e.g., `microx`), use that.

### **Interacting with micro\_X**

* **Direct Commands:** Type any Linux command and press Enter.
    ```
    (~) > ls -l
    ```
* **AI Translation:** Prefix your query with `/ai`.
    ```
    (~) > /ai list all python files in my documents folder
    ```
* **Command Management:** Use `/command help` to see how to add, remove, list, or move categorized commands.
    ```
    (~) > /command list
    (~) > /command add "my_custom_script.sh --interactive" interactive_tui
    ```
* **Utilities:** Run scripts from the `utils` directory.
    ```
    (~) > /utils list
    (~) > /utils generate_tree
    ```
* **Update:** Check for and pull updates.
    ```
    (~) > /update
    ```
* **Navigation & Control:**
    * `Ctrl+C` / `Ctrl+D`: Exit micro\_X or cancel current categorization prompt.
    * `Enter`: Submit command/query.
    * `Up/Down Arrows`: Navigate command history / input lines.
    * `Tab`: Attempt completion / indent.
    * `PgUp/PgDn`: Scroll output area.

## **Configuration**

micro\_X uses a hierarchical configuration system:

1.  **Fallback Configuration:** Hardcoded defaults within `main.py`.
2.  **Default Configuration Files (in `config/` directory):**
    * `config/default_config.json`: Defines default AI models, their prompts, timeouts, UI behavior, and paths.
        * `ai_models`: Specifies the Ollama models for `primary_translator`, `direct_translator`, and `validator`.
        * `prompts`: Contains system and user prompt templates for each AI model role.
        * `behavior`: Includes settings like `input_field_height`, `default_category_for_unclassified`, AI retry attempts, and the TUI detection thresholds:
            * `tui_detection_line_threshold_pct` (default: 30.0): Min percentage of lines with ANSI codes to flag as TUI.
            * `tui_detection_char_threshold_pct` (default: 3.0): Min percentage of characters being ANSI codes to flag as TUI.
        * Other keys control timeouts, UI elements, etc.
    * `config/default_command_categories.json`: Pre-populates commands into `simple`, `semi_interactive`, and `interactive_tui` categories.
3.  **User Configuration Files (in `config/` directory - you create these to override defaults):**
    * `config/user_config.json`: Your overrides for any settings in `default_config.json`.
    * `config/user_command_categories.json`: Your custom command categorizations or overrides to the defaults. User settings take precedence.

* **Command History:** Stored in `.micro_x_history` in the project root.
* **Logs:** Written to `logs/micro_x.log`.
* **Tmux Configuration:** The `micro_X.sh` launch script uses `config/.tmux.conf` to set up the `tmux` session for micro\_X. You can customize this file for aspects like default shell within the `tmux` session if needed, though `main.py` is the primary application launched.
* **OLLAMA\_HOST (for WSL):** Refer to `setup_micro_x_wsl.md` for configuring this environment variable if running Ollama on the Windows host and micro\_X in WSL.

## **Future Ideas & Contributions**

* Enhanced parsing for AI output.
* More sophisticated security sandboxing.
* User-configurable AI parameters (temperature, etc.) directly via commands or UI.
* Support for more advanced `tmux` integrations.
* Plugin system for extending functionality.

Contributions, bug reports, and feature requests are welcome! Please open an issue or pull request on the [GitHub repository](https://github.com/thurtz/micro_X.git).

*This README was drafted with the assistance of an AI and subsequently updated based on project evolution.*
