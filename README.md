# **micro\_X: The AI-Enhanced Shell**

**micro\_X** is an intelligent, interactive shell environment designed to bridge the gap between natural language and executable Linux commands. It leverages local large language models (LLMs) via Ollama to translate your queries, validate commands, explain their functionality, and streamline your command-line workflow.

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

## **Key Features**

* **Natural Language to Command Translation:** Uses a configurable "primary\_translator" Ollama model for initial translation (default example: llama3.2:3b).  
* **Optional Secondary Direct Translator:** Can leverage a configurable "direct\_translator" model specialized in direct command output (default example: vitali87/shell-commands-qwen2-1.5b) as a fallback or alternative.  
* **AI-Powered Command Validation:** Employs a configurable "validator" Ollama model (default example: herawen/lisa:latest) to assess command validity.  
* **AI-Powered Command Explanation:** Before executing an AI-generated command, you can request an explanation from a configurable "explainer" Ollama model (default example: llama3.2:3b) to understand its purpose and potential impact.  
* **Interactive Command Confirmation:** For AI-generated commands, micro\_X prompts for user action:  
  * \[Y\]es: Execute the command (will prompt for categorization if the command is new).  
  * \[Ys\] Simple & Run: Execute and categorize the command as 'simple'.  
  * \[Ym\] Semi-Interactive & Run: Execute and categorize the command as 'semi\_interactive'.  
  * \[Yi\] TUI & Run: Execute and categorize the command as 'interactive\_tui'.  
  * \[E\]xplain: Ask the AI to explain the command before deciding.  
  * \[M\]odify: Load the command into the input field for editing.  
  * \[C\]ancel: Do not execute the command.  
* **Command Categorization & Execution:**  
  * simple: Direct execution, output captured in micro\_X.  
  * semi\_interactive: Runs in a new tmux window. Output is typically captured after completion.  
    * **Smart Output Handling:** If a semi\_interactive command produces output resembling a full-screen TUI application, micro\_X avoids displaying garbled output and suggests re-categorizing to interactive\_tui.  
  * interactive\_tui: Runs fully interactively in a new tmux window.  
  * Users manage categories via /command subcommands.  
* **Ollama Service Management (/ollama command):**  
  * Control the Ollama service directly from micro\_X.  
  * Subcommands: start, stop, restart, status, help.  
* **Modular Architecture:**  
  * modules/ai\_handler.py: Manages all interactions with Ollama LLMs.  
  * modules/category\_manager.py: Handles command categories.  
  * modules/output\_analyzer.py: Detects TUI-like output.  
  * modules/ollama\_manager.py: Manages the Ollama service lifecycle.  
* **Shell-like Functionality:** Supports cd, history, and shell variable expansion.  
* **Security:** Basic sanitization for potentially dangerous commands. The command confirmation flow with the "Explain" option is a key safety feature. **Always review and understand commands, especially AI-generated ones, before execution.**  
* **Logging & Configuration:** Detailed logging and persistent configuration.

## **Supported Platforms & Setup**

micro\_X is designed to be adaptable. A unified setup script (setup.sh) in the project root will attempt to detect your OS or allow you to choose the appropriate configuration. This script then calls an OS-specific helper script located in the setup\_scripts/ directory.

Detailed manual instructions and prerequisites for each platform are also available in the docs/ directory:

* **Linux Mint (and compatible Debian-based systems):**  
  * Unified setup via: ./setup.sh (select or auto-detects Mint/Debian/Ubuntu)  
  * Detailed OS-specific instructions: docs/setup\_micro\_X\_mint.md  
* **macOS:**  
  * Unified setup via: ./setup.sh (select or auto-detects macOS)  
  * Detailed OS-specific instructions: docs/setup\_micro\_X\_mac.md  
* **Termux (Android):**  
  * Unified setup via: ./setup.sh (select or auto-detects Termux)  
  * Detailed OS-specific instructions: docs/setup\_micro\_X\_termux.md  
* **WSL (Windows Subsystem for Linux):**  
  * Unified setup via: ./setup.sh (select or auto-detects WSL)  
  * Detailed OS-specific instructions: docs/setup\_micro\_X\_wsl.md

**General Prerequisites (Common across platforms, details in specific setup guides):**

* Python 3.8+  
* pip3 & python3-venv (or equivalent Python virtual environment tools)  
* tmux (Required for semi\_interactive and interactive\_tui commands)  
* Ollama ([ollama.com](https://ollama.com/)) installed and running.  
* **Required Ollama Models (Examples \- these are configurable):**  
  * Pull via ollama pull \<model\_name\> (e.g., ollama pull llama3.2:3b)  
  * Primary Translator (e.g., llama3.2:3b)  
  * Direct Translator (e.g., vitali87/shell-commands-qwen2-1.5b)  
  * Validator (e.g., herawen/lisa:latest)  
  * Explainer (e.g., llama3.2:3b)

**General Setup Steps:**

1. **Clone the Repository:**  
   git clone https://github.com/thurtz/micro\_X.git  
   cd micro\_X

2. **Make the Unified Setup Script Executable:**  
   chmod \+x setup.sh

3. **Run the Unified Setup Script:**  
   ./setup.sh

   * The script will attempt to detect your OS.  
   * If detection is successful, it will confirm before proceeding or offer a menu.  
   * If detection is uncertain, it will present a menu to choose your OS/environment.  
   * The script will then guide you through installing dependencies, setting up the Python environment, and Ollama model guidance. Follow the on-screen prompts.

## **Usage**

1. **Ensure Ollama is Running** (use /ollama status within micro\_X or check externally).  
2. **Launch micro\_X:**  
   * **Desktop Menu:** If installed (Linux Mint), look for "micro\_X".  
   * **Using the Launch Script (Recommended):** From the micro\_X directory:  
     ./micro\_X.sh

   * **Manually:**  
     source .venv/bin/activate  
     python3 main.py

### **Interacting with micro\_X**

* **Direct Commands:** Type any Linux command and press Enter (e.g., ls \-l).  
* **AI Translation (/ai):** Prefix your query with /ai.  
  (\~) \> /ai list all python files in my documents folder

  If the AI suggests a command, you'll be prompted to confirm, explain, modify, or cancel it.  
* **Command Management (/command):** Use /command help for options to add, remove, list, or move categorized commands.  
  (\~) \> /command list  
  (\~) \> /command add "my\_custom\_script.sh \--interactive" interactive\_tui

* **Ollama Management (/ollama):** Control the Ollama service.  
  (\~) \> /ollama status  
  (\~) \> /ollama start  
  (\~) \> /ollama help

* **Utilities (/utils):** Run scripts from the utils directory.  
  (\~) \> /utils list  
  (\~) \> /utils generate\_tree

* **Update (/update):** Check for and pull updates for micro\_X.  
* **Help (/help):** Displays the main help message.  
* **Navigation & Control:**  
  * Ctrl+C / Ctrl+D: Exit micro\_X or cancel current categorization/confirmation.  
  * Enter: Submit command/query.  
  * Up/Down Arrows: Navigate command history / input lines.  
  * Tab: Attempt completion / indent.  
  * PgUp/PgDn: Scroll output area.

## **Configuration**

micro\_X uses a hierarchical configuration system (fallback \-\> default \-\> user):

* **Default Configuration:** config/default\_config.json (AI models, prompts, timeouts, behavior).  
* **User Configuration:** config/user\_config.json (Your overrides).  
* **Default Command Categories:** config/default\_command\_categories.json.  
* **User Command Categories:** config/user\_command\_categories.json (Your categorizations).  
* **Command History:** .micro\_x\_history (project root).  
* **Logs:** logs/micro\_x.log.  
* **Tmux Configuration:** config/.tmux.conf (used by micro\_X.sh).

## **Security Considerations**

* **AI-Generated Commands:** While micro\_X includes AI validation and a basic command sanitizer, **AI can still generate unexpected or harmful commands.**  
* **Review and Understand:** Always use the \[E\]xplain option in the confirmation flow for AI-generated commands if you are unsure about their function. Modify or cancel commands if they seem suspicious.  
* **User Responsibility:** You are responsible for the commands executed in your environment.

## **Future Ideas & Contributions**

* Enhanced parsing for AI output.  
* More sophisticated security sandboxing options.  
* User-configurable AI parameters (temperature, etc.) directly via commands.  
* Plugin system for extending functionality.

Contributions, bug reports, and feature requests are welcome\! Please open an issue or pull request on the [GitHub repository](https://github.com/thurtz/micro_X.git).

*This README was drafted with the assistance of an AI and subsequently updated based on project evolution.*