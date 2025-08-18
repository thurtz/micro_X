# **micro\_X: The AI-Enhanced Shell**

micro\_X is an intelligent, interactive shell environment designed to bridge the gap between natural language and executable Linux commands. It leverages local large language models (LLMs) via Ollama to translate your queries, validate commands, explain their functionality, and streamline your command-line workflow. It also features branch-aware integrity checks to ensure code reliability when running on stable or testing branches.  
GitHub Repository: https://github.com/thurtz/micro\_X.git  
Detailed User Guide: docs/user\_guide/index.md

## **Overview**

micro\_X provides a text-based user interface (TUI) where you can:

* Type standard Linux commands.  
* Force natural language queries (prefixed with /ai) to have them translated into shell commands.  
* Benefit from AI-powered validation and translation of natural language (without the need for /ai prefixed) or directly entered commands.  
* **Confirm AI-Generated Commands:** Review, get explanations, modify, or cancel commands suggested by the AI before execution.  
* Categorize commands (simple, semi\_interactive, interactive\_tui) for appropriate execution, including running interactive commands in tmux.  
* **Run Custom Scripts:** Add your own Python scripts to a dedicated user\_scripts/ directory and run them with the /run command.  
* **Create Command Aliases:** Use the built-in alias utility to create shortcuts for your favorite or frequently used commands.  
* Manage command history and categorizations.  
* Control the underlying Ollama service directly from within the shell.  
* **Branch-Aware Integrity & Developer Mode:** Automatically enables a permissive 'Developer Mode' when running off the dev branch. Performs startup integrity checks on main and testing branches.  
* **Web-Based Configuration Manager:** An integrated tool to easily view and edit user configurations and command categorizations via a web interface (launched with the **/config** command).

## **Key Features**

* **Natural Language to Command Translation:** Uses a configurable "primary\_translator" Ollama model for initial translation (default example: vitali87/shell-commands-qwen2-1.5b-q8\_0-extended).  
* **Secondary Direct Translator:** Leverages a configurable "direct\_translator" model specialized in direct command output (default example: vitali87/shell-commands-qwen2-1.5b-extended) as a fallback.  
* **AI-Powered Command Validation:** Employs a configurable "validator" Ollama model (default example: herawen/lisa) to assess command validity.  
* **AI-Powered Command Explanation:** Before executing an AI-generated command, you can request an explanation from a configurable "explainer" Ollama model (default example: herawen/lisa) to understand its purpose and potential impact.  
* **Interactive Command Confirmation:** For AI-generated commands, micro\_X prompts for user action:  
  * \[Y\]es: Execute the command (will prompt for categorization if the command is new).  
  * \[Ys\] Simple & Run: Execute and categorize the command as 'simple'.  
  * \[Ym\] Semi-Interactive & Run: Execute and categorize the command as 'semi\_interactive'.  
  * \[Yi\] TUI & Run: Execute and categorize the command as 'interactive\_tui'.  
  * \[E\]xplain: Ask the AI to explain the command before deciding.  
  * \[M\]odify: Load the command into the input field for editing.  
  * \[C\]ancel: Do not execute the command.  
* **Command Categorization & Execution:** \* simple: Direct execution, output captured in micro\_X.  
  * semi\_interactive: Runs in a new tmux window. Output is typically captured after completion.  
    * Smart Output Handling: If a semi\_interactive command produces output resembling a full-screen TUI application, micro\_X avoids displaying garbled output and suggests re-categorizing to interactive\_tui.  
  * interactive\_tui: Runs fully interactively in a new tmux window.  
  * Users manage categories via the **/command** alias.  
* **Ollama Service Management (/ollama command):** \* Control the Ollama service directly from micro\_X.  
  * Subcommands: start, stop, restart, status, help.  
* **Runtime AI Configuration (/config command):** \* View and modify AI model settings (e.g., model name, temperature) at runtime.  
  * Save runtime changes to your user configuration file.  
* **Branch-Aware Integrity & Developer Mode:** \* Developer Mode: Automatically activated when running from the dev branch or if integrity checks cannot be performed (e.g., not a git repository). In this mode, integrity checks are informational or bypassed, allowing development and local modifications without interruption.  
  * Protected Mode: Active when running from main or testing branches. Performs startup integrity checks:  
    * Clean Working Directory: Ensures no uncommitted changes to tracked files.  
    * Sync with Remote: Verifies the local branch is synchronized with its remote counterpart (origin/main or origin/testing).  
    * If critical integrity checks fail (e.g., uncommitted local changes on a protected branch), micro\_X will halt execution. If the local branch is merely behind the remote, it will issue a warning and suggest using /update (if allow\_run\_if\_behind\_remote is enabled in config, which is default). Error messages are logged to logs/micro\_x.log.  
* **Modular Architecture:** \* modules/ai\_handler.py: Manages all interactions with Ollama LLMs.  
  * modules/category\_manager.py: Handles command categories.  
  * modules/output\_analyzer.py: Detects TUI-like output.  
  * modules/ollama\_manager.py: Manages the Ollama service lifecycle.  
  * modules/shell\_engine.py: Orchestrates command processing and execution.  
  * modules/git\_context\_manager.py: Handles Git interactions for integrity checks.  
* **Shell-like Functionality:** Supports cd, history, and shell variable expansion.  
* **Multi-Layered Security**: micro\_X employs a multi-layered security approach. It uses a configurable **deny-list** in config/default\_config.json to automatically block known dangerous command patterns. Additionally, a separate **warn-list** triggers an extra confirmation prompt for sensitive commands (like fdisk or dd) that aren't blocked outright. The primary defense for all AI-generated commands remains the interactive **user confirmation flow** (\[E\]xplain, \[M\]odify, \[C\]ancel), ensuring you always have the final say before execution.  
* **Logging & Configuration:** Detailed logging and persistent configuration.  
* **Web-Based Configuration Manager:** Launch with the **/config** command to easily manage user\_config.json and user\_command\_categories.json via a web UI.

## **Setup Guide**

### **Step 1: General Setup**

It is recommended that all users start by cloning and setting up the main branch for the most stable experience.

1. Clone the Repository:  
   git clone https://github.com/thurtz/micro\_X.git  
   cd micro\_X  
2. Make the Setup Script Executable:  
   chmod \+x setup.sh  
3. Run the Unified Setup Script:  
   ./setup.sh  
   * The script will guide you through installing dependencies, setting up the Python environment, and pulling the necessary Ollama models. Follow the on-screen prompts.

### **Step 2 (Optional): For Developers and Testers**

If you wish to contribute to development or test new features, you can activate the development environment from your stable main branch installation.

1. Launch micro\_X from your main branch installation:  
   ./micro\_X.sh  
2. Run the Activation Utility: Inside micro\_X, run the following command:  
   /dev \--activate  
   * This command will clone the testing and dev branches into new subdirectories (micro\_X-testing/ and micro\_X-dev/) and run the setup process for each of them.  
   * You will then have three separate, managed installations of micro\_X.

## **Usage**

1. **Ensure Ollama is Running** (use /ollama status within micro\_X or check externally).  
2. **Launch micro\_X:**  
   * From your micro\_X (main) directory, run: ./micro\_X.sh  
   * To run the dev version, navigate to its directory and run its launch script: cd micro\_X-dev && ./micro\_X.sh

### **Operational Modes (Based on Git Branch)**

micro\_X's behavior at startup is influenced by the current Git branch:

* **Developer Mode:** Automatically active if you are on the dev branch. In this mode, startup integrity checks are informational and do not halt execution, allowing for local code changes.  
* **Protected Mode:** Active if you are on the main or testing branches. micro\_X performs strict integrity checks to ensure the code is clean and synced with the remote repository. If these checks fail, the application will halt to prevent running on potentially unstable code.

### **Interacting with micro\_X**

* **Direct Commands:** Type any Linux command and press Enter (e.g., ls \-l).  
* **AI Translation (/ai):** Prefix your query with /ai to translate it into a command.  
  * (\~) \> /ai list text files  
* **User Scripts (/run):** Execute your own scripts from the user\_scripts/ directory.  
  * (\~) \> /run my\_script \--with-args  
* **Aliases (/alias, /command, /config, etc.):** Use aliases for common utilities.  
  * (\~) \> /alias \--add /snap /snapshot  
  * (\~) \> /config \--start  
* **Help (/help):** Displays the main help message.  
* **Exit (/exit or exit):** Exits the micro\_X shell.

## **Troubleshooting**

* **Integrity Check Failed:** If micro\_X halts on startup on the main or testing branch, it means your local code has uncommitted changes or is not synced with the official repository.  
  * **Solution:** Open a standard terminal in the project directory. Use git status to see the changes. You can either discard them (git reset \--hard origin/main) or commit them on a separate feature branch. For development, it's best to switch to the dev branch (git checkout dev).

## **Future Ideas & Contributions**

* More sophisticated security sandboxing options.  
* Plugin system for extending functionality.  
* GPG signature verification for commits/tags on the main branch as part of integrity checks.

## **Minor Areas for Potential Refinement**

The project is in an excellent state, and the following points are minor suggestions for future evolution rather than immediate flaws:

* **Configuration File Format**: The configuration files \(e.g., default\_config.json\) now support comments \(like JSONC\) for better self\-documentation, even while retaining the .json extension. A future migration to a more structured format like TOML is still being considered for long\-term maintainability.
* **Dependency Injection**: In main.py, module references are passed to the ShellEngine. A slightly cleaner pattern could be to pass fully initialized instances of the managers. This is a minor stylistic point with no impact on current functionality.

Contributions, bug reports, and feature requests are welcome\! Please open an issue or pull request on the GitHub repository.  
This README was drafted with the assistance of an AI and subsequently updated based on project evolution.