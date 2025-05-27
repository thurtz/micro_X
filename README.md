# **micro\_X: The AI-Enhanced Shell**

**micro\_X** is an intelligent, interactive shell environment designed to bridge the gap between natural language and executable Linux commands. It leverages local large language models (LLMs) via Ollama to translate your queries, validate commands, explain their functionality, and streamline your command-line workflow. It also features branch-aware integrity checks to ensure code reliability when running on stable or testing branches.

GitHub Repository: https://github.com/thurtz/micro\_X.git

Detailed User Guide: docs/micro\_X\_User\_Guide.md

## **Overview**

micro\_X provides a text-based user interface (TUI) where you can:

* Type standard Linux commands.
* Enter natural language queries (prefixed with /ai) to have them translated into shell commands.
* Benefit from AI-powered validation of translated or directly entered commands.
* **Confirm AI-Generated Commands:** Review, get explanations, modify, or cancel commands suggested by the AI before execution.
* Categorize commands (simple, semi\_interactive, interactive\_tui) for appropriate execution, including running interactive commands in tmux.
* Manage command history and categorizations.
* Control the underlying Ollama service directly from within the shell.
* **Branch-Aware Integrity & Developer Mode:** Automatically enables a permissive 'Developer Mode' when running off the dev branch. Performs startup integrity checks on main and testing branches.

## **Key Features**

* **Natural Language to Command Translation:** Uses a configurable "primary\_translator" Ollama model for initial translation (default example: llama3.2:3b).
* **Optional Secondary Direct Translator:** Can leverage a configurable "direct\_translator" model specialized in direct command output (default example: vitali87/shell-commands-qwen2-1.5b) as a fallback or alternative.
* **AI-Powered Command Validation:** Employs a configurable "validator" Ollama model (default example: herawen/lisa:latest) to assess command validity.
* **AI-Powered Command Explanation:** Before executing an AI-generated command, you can request an explanation from a configurable "explainer" Ollama model (default example: llama3.2:3b) to understand its purpose and potential impact.
* **Interactive Command Confirmation:** For AI-generated commands, micro\_X prompts for user action:
  * \[Y]es: Execute the command (will prompt for categorization if the command is new).
  * \[Ys] Simple & Run: Execute and categorize the command as 'simple'.
  * \[Ym] Semi-Interactive & Run: Execute and categorize the command as 'semi\_interactive'.
  * \[Yi] TUI & Run: Execute and categorize the command as 'interactive\_tui'.
  * \[E]xplain: Ask the AI to explain the command before deciding.
  * \[M]odify: Load the command into the input field for editing.
  * \[C]ancel: Do not execute the command.
* **Command Categorization & Execution:** \* simple: Direct execution, output captured in micro\_X.
  * semi\_interactive: Runs in a new tmux window. Output is typically captured after completion.
    * **Smart Output Handling:** If a semi\_interactive command produces output resembling a full-screen TUI application, micro\_X avoids displaying garbled output and suggests re-categorizing to interactive\_tui.
  * interactive\_tui: Runs fully interactively in a new tmux window.
  * Users manage categories via /command subcommands.
* **Ollama Service Management (/ollama command):** \* Control the Ollama service directly from micro\_X.
  * Subcommands: start, stop, restart, status, help.
* **Branch-Aware Integrity & Developer Mode:** \* **Developer Mode:** Automatically activated when running from the dev branch or if integrity checks cannot be performed (e.g., not a git repository). In this mode, integrity checks are informational or bypassed, allowing development and local modifications without interruption.
  * **Protected Mode:** Active when running from main or testing branches. Performs startup integrity checks:
    * **Clean Working Directory:** Ensures no uncommitted changes to tracked files.
    * **Sync with Remote:** Verifies the local branch is synchronized with its remote counterpart (origin/main or origin/testing).
    * If critical integrity checks fail (e.g., uncommitted local changes on a protected branch), micro\_X will **halt execution**. If the local branch is merely behind the remote, it will issue a warning and suggest using `/update` (if `allow_run_if_behind_remote` is enabled in config, which is default). Error messages are logged to `logs/micro_x.log`.
* **Modular Architecture:** \* modules/ai\_handler.py: Manages all interactions with Ollama LLMs.
  * modules/category\_manager.py: Handles command categories.
  * modules/output\_analyzer.py: Detects TUI-like output.
  * modules/ollama\_manager.py: Manages the Ollama service lifecycle.
  * modules/shell\_engine.py: Orchestrates command processing and execution.
  * modules/git\_context\_manager.py: Handles Git interactions for integrity checks.
* **Shell-like Functionality:** Supports cd, history, and shell variable expansion.
* **Security:** Basic sanitization for potentially dangerous commands. The command confirmation flow with the "Explain" option and startup integrity checks are key safety features. **Always review and understand commands, especially AI-generated ones, before execution.** \* **Logging & Configuration:** Detailed logging and persistent configuration.

## **Choosing a Branch & Setup**

* **For most users, the `main` branch is recommended for the most stable experience.**
* The `testing` branch contains features that are being prepared for release and may be less stable.
* The `dev` branch is for active development and may contain experimental or unstable features.

micro\_X is designed to be adaptable. A unified setup script (setup.sh) in the project root will attempt to detect your OS or allow you to choose the appropriate configuration. This script then calls an OS-specific helper script located in the setup\_scripts/ directory.

**Important:** For full functionality, including developer mode and integrity checks, micro\_X should be run from a git clone of the repository with git installed and accessible in your system's PATH.

Detailed manual instructions and prerequisites for each platform are also available in the docs/ directory:

* **Linux Mint (and compatible Debian-based systems):** \* Unified setup via: ./setup.sh (select or auto-detects Mint/Debian/Ubuntu)
  * Detailed OS-specific instructions: docs/setup\_micro\_X\_mint.md
* **macOS:** \* Unified setup via: ./setup.sh (select or auto-detects macOS)
  * Detailed OS-specific instructions: docs/setup\_micro\_X\_mac.md
* **Termux (Android):** \* Unified setup via: ./setup.sh (select or auto-detects Termux)
  * Detailed OS-specific instructions: docs/setup\_micro\_X\_termux.md
* **WSL (Windows Subsystem for Linux):** \* Unified setup via: ./setup.sh (select or auto-detects WSL)
  * Detailed OS-specific instructions: docs/setup\_micro\_X\_wsl.md

**General Prerequisites (Common across platforms, details in specific setup guides):**

* Python 3.8+
* pip3 & python3-venv (or equivalent Python virtual environment tools)
* tmux (Required for semi\_interactive and interactive\_tui commands)
* **Git:** Required for updates and the new integrity check features.
* Ollama ([ollama.com](https://ollama.com/)) installed and running.
* **Required Ollama Models (Examples - these are configurable):** \* Pull via ollama pull <model\_name> (e.g., ollama pull llama3.2:3b)
  * Primary Translator (e.g., llama3.2:3b)
  * Direct Translator (e.g., vitali87/shell-commands-qwen2-1.5b)
  * Validator (e.g., herawen/lisa:latest)
  * Explainer (e.g., llama3.2:3b)

**Managing Multiple Branches (Optional):**

If you want to work with or test different branches simultaneously, you can clone the repository into separate directories:

1.  **Main Branch (Stable):**
    ```bash
    git clone [https://github.com/thurtz/micro_X.git](https://github.com/thurtz/micro_X.git) micro_X-main
    cd micro_X-main
    # git checkout main # Usually already on main
    ./setup.sh # Run setup within this directory
    ```
2.  **Testing Branch:**
    ```bash
    git clone [https://github.com/thurtz/micro_X.git](https://github.com/thurtz/micro_X.git) micro_X-testing
    cd micro_X-testing
    git checkout testing
    ./setup.sh # Run setup within this directory
    ```
3.  **Development Branch:**
    ```bash
    git clone [https://github.com/thurtz/micro_X.git](https://github.com/thurtz/micro_X.git) micro_X-dev
    cd micro_X-dev
    git checkout dev
    ./setup.sh # Run setup within this directory
    ```
Each directory will have its own independent micro\_X installation and virtual environment.

**General Setup Steps (for a single clone):**

1. Clone the Repository:
   git clone https://github.com/thurtz/micro\_X.git
   cd micro\_X
2. Make the Unified Setup Script Executable:
   chmod +x setup.sh
3. Run the Unified Setup Script:
   ./setup.sh
   * The script will attempt to detect your OS.
   * If detection is successful, it will confirm before proceeding or offer a menu.
   * If detection is uncertain, it will present a menu to choose your OS/environment.
   * The script will then guide you through installing dependencies, setting up the Python environment, and Ollama model guidance. Follow the on-screen prompts.

## **Usage**

1. **Ensure Ollama is Running** (use /ollama status within micro\_X or check externally).
2. **Launch micro\_X:** \* **Desktop Menu:** If installed (Linux Mint), look for "micro\_X".
   * Using the Launch Script (Recommended): From the micro\_X directory:
     ./micro\_X.sh
   * **Manually:** From the micro\_X directory:
     source .venv/bin/activate
     tmux -f config/.tmux.conf new-session -A -s micro\_X
     python3 main.py

### **Operational Modes (Based on Git Branch)**

micro\_X's behavior at startup is influenced by the current Git branch:

* **Developer Mode:** \* Automatically active if you are on the dev branch, or if micro\_X cannot perform integrity checks (e.g., not run from a git repository, or git command is unavailable).
  * In this mode, startup integrity checks are informational or bypassed. micro\_X will run even if there are local code changes or if the branch is not synced with its remote.
  * This mode is intended for active development.
* **Protected Mode:** \* Active if you are on the main or testing branches.
  * micro\_X performs integrity checks at startup:
    1. **Clean Working Directory:** Verifies no uncommitted local changes to tracked files.
    2. **Sync with Remote:** Verifies the local branch is synchronized with its counterpart on origin (e.g., origin/main).
  * **If checks fail:**
    * If critical issues are found (e.g., uncommitted local changes, local branch ahead of or diverged from remote), micro\_X will display an error message and **halt execution**. Check `logs/micro_x.log` for details if the UI closes too quickly.
    * If the local branch is merely *behind* the remote (and `allow_run_if_behind_remote` is true in config), a warning will be shown, and `/update` will be suggested.
  * See the User Guide or Troubleshooting section for how to resolve these issues.

### **Interacting with micro\_X**

* **Direct Commands:** Type any Linux command and press Enter (e.g., ls -l).
* AI Translation (/ai): Prefix your query with /ai.
  (\~) > /ai list all python files in my documents folder
  If the AI suggests a command, you'll be prompted to confirm, explain, modify, or cancel it.
* Command Management (/command): Use /command help for options to add, remove, list, or move categorized commands.
  (\~) > /command list
  (\~) > /command add "my\_custom\_script.sh --interactive" interactive\_tui
* Ollama Management (/ollama): Control the Ollama service.
  (\~) > /ollama status
  (\~) > /ollama start
  (\~) > /ollama help
* Utilities (/utils): Run scripts from the utils directory.
  (\~) > /utils list
  (\~) > /utils generate\_tree
  (\~) > /utils generate\_snapshot help (or -h, --help)
* **Update (/update):** Check for and pull updates for micro\_X.
* **Help (/help):** Displays the main help message.
* **Navigation & Control:** \* Ctrl+C / Ctrl+D: Exit micro\_X or cancel current categorization/confirmation/edit.
  * Enter: Submit command/query.
  * Up/Down Arrows: Navigate command history / input lines.
  * Tab: Attempt completion / indent.
  * PgUp/PgDn: Scroll output area.

## **Configuration**

micro\_X uses a hierarchical configuration system (fallback -> default -> user):

* **Default Configuration:** config/default\_config.json (AI models, prompts, timeouts, behavior, integrity check settings).
* **User Configuration:** config/user\_config.json (Your overrides).
* **Default Command Categories:** config/default\_command\_categories.json.
* **User Command Categories:** config/user\_command\_categories.json (Your categorizations).
* **Command History:** .micro\_x\_history (project root).
* **Logs:** logs/micro\_x.log.
* **Tmux Configuration:** config/.tmux.conf (used by micro\_X.sh).

## **Security Considerations**

* **AI-Generated Commands:** While micro\_X includes AI validation and a basic command sanitizer, **AI can still generate unexpected or harmful commands.** \* **Review and Understand:** Always use the \[E]xplain option in the confirmation flow for AI-generated commands if you are unsure about their function. Modify or cancel commands if they seem suspicious.
* **Startup Integrity Checks:** The checks on main and testing branches provide an added layer of assurance against unintentional or unauthorized local code modifications.
* **User Responsibility:** You are responsible for the commands executed in your environment.

## **Troubleshooting**

* **micro\_X halts on startup mentioning 'Integrity Check Failed' on main or testing branch:** \* *Reason:* Your local copy of the branch has uncommitted changes or is not synchronized with the official remote version (origin/main or origin/testing) in a way that prevents safe execution (e.g., local changes, ahead of remote). If micro\_X closes too quickly to read the message, check `logs/micro_x.log` for details.
  * *Solution:* 1. Open a standard terminal in your micro\_X project directory.
    2\. Check status: git status
    3\. If you have local changes:
    * Commit them: git add . && git commit -m "Your changes" (then git pull --rebase and git push if intended for upstream).
    * Stash them: git stash (you can apply later with git stash pop).
    * Discard them: git reset --hard HEAD (Warning: This permanently deletes uncommitted changes).
    4. Ensure you are synced with the remote: `git fetch origin` then `git pull origin <branchname>` (e.g., `main`). If you are ahead and want to discard local commits: `git reset --hard origin/<branchname>`. **Use reset --hard with extreme caution.**
    5. If you intend to develop, switch to the `dev` branch: `git checkout dev`.
* **micro\_X shows warnings about being behind remote:**
    * *Reason:* Your local protected branch is behind the remote.
    * *Solution:* Run `/update` within micro\_X, or `git pull` in a standard terminal in the project directory.


## **Future Ideas & Contributions**

* Enhanced parsing for AI output.
* More sophisticated security sandboxing options.
* User-configurable AI parameters (temperature, etc.) directly via commands.
* Plugin system for extending functionality.
* GPG signature verification for commits/tags on the main branch as part of integrity checks.

Contributions, bug reports, and feature requests are welcome! Please open an issue or pull request on the [GitHub repository](https://github.com/thurtz/micro_X.git).

*This README was drafted with the assistance of an AI and subsequently updated based on project evolution.*
