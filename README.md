# **micro\_X: The AI-Enhanced Shell**

**micro\_X** is an intelligent, interactive shell environment designed to bridge the gap between natural language and executable Linux commands. It leverages local large language models (LLMs) via Ollama to translate your queries, validate commands, and streamline your command-line workflow.

**GitHub Repository:** [https://github.com/thurtz/micro\_X.git](https://github.com/thurtz/micro_X.git)

## **Overview**

micro\_X provides a text-based user interface (TUI) where you can:

* Type standard Linux commands.  
* Enter natural language queries (prefixed with /ai) to have them translated into shell commands.  
* Benefit from AI-powered validation of translated or directly entered commands.  
* Categorize commands (simple, semi\_interactive, interactive\_tui) for appropriate execution, including running interactive commands in tmux.  
* Manage command history and categorizations.

## **Key Features**

* **Natural Language to Command Translation:** Uses a primary Ollama model (e.g., llama3.2:3b) for initial translation.  
* **Optional Secondary Direct Translator:** Can leverage a model specialized in direct command output (e.g., vitali87/shell-commands-qwen2-1.5b) as a fallback or alternative.  
* **AI-Powered Command Validation:** Employs a validator Ollama model (e.g., herawen/lisa:latest) to assess command validity.  
* **Command Categorization:**  
  * simple: Direct execution, output captured in micro\_X.  
  * semi\_interactive: Runs in a new tmux window, output captured after completion.  
  * interactive\_tui: Runs fully interactively in a new tmux window.  
  * Users can manage these categories via /command subcommands.  
* **Chained Command Support:** Capable of processing and executing commands linked by &&, ||, |, etc.  
* **Interactive TUI:** Built with prompt\_toolkit for a user-friendly experience.  
* **Shell-like Functionality:** Supports cd, history, and shell variable expansion.  
* **Security:** Basic sanitization for potentially dangerous commands.  
* **Logging & Configuration:** Detailed logging and persistent configuration for categories and history.

## **Supported Platforms & Setup**

micro\_X is designed to be adaptable and has specific setup guidance for the following environments:

* **Linux Mint (and compatible Debian-based systems):**  
  * Automated setup script: setup.sh (or setup\_micro\_x\_mint.sh)  
  * Detailed instructions: [setup\_micro\_x\_mint.md](http://docs.google.com/setup_micro_x_mint.md)  
* **macOS:**  
  * Automated setup script: setup\_micro\_x\_mac.sh  
  * Detailed instructions: [setup\_micro\_x\_mac.md](http://docs.google.com/setup_micro_x_mac.md)  
* **Termux (Android):**  
  * Setup script (guides through Termux-specific steps): setup\_micro\_x\_termux.sh  
  * Detailed instructions: [setup\_micro\_x\_termux.md](http://docs.google.com/setup_micro_x_termux.md)  
* **WSL (Windows Subsystem for Linux):**  
  * Setup script (for within WSL, assumes Ollama on Windows host): setup\_micro\_x\_wsl.sh  
  * Detailed instructions: [setup\_micro\_x\_wsl.md](http://docs.google.com/setup_micro_x_wsl.md)

**General Prerequisites (Common across platforms, details in specific setup guides):**

* Python 3.8+  
* pip3 & python3-venv  
* tmux  
* Ollama ([ollama.com](https://ollama.com/)) installed and running.  
* Required Ollama Models (pulled via ollama pull \<model\_name\>):  
  * llama3.2:3b (or your chosen primary translator)  
  * vitali87/shell-commands-qwen2-1.5b (or your chosen direct translator)  
  * herawen/lisa:latest (or your chosen validator)

**General Setup Steps (Refer to specific platform .md files for details):**

1. **Clone the Repository:**  
   git clone https://github.com/thurtz/micro\_X.git  
   cd micro\_X

2. **Run the Appropriate Setup Script** for your platform (e.g., ./setup.sh or ./setup\_micro\_x\_mac.sh). These scripts typically:  
   * Check and help install system dependencies.  
   * Guide Ollama setup and model pulling.  
   * Create a Python virtual environment (.venv).  
   * Install Python packages from requirements.txt.  
   * Make scripts executable.  
   * Handle platform-specific configurations (like .desktop files or aliases).

## **Usage**

1. **Ensure Ollama is Running** (on your host machine or as per your platform's setup).  
2. **Launch micro\_X:**  
   * **Desktop Menu:** If a .desktop entry was installed (Linux Mint), look for "micro\_X".  
   * **Using the Launch Script (Recommended for Terminal):**  
     ./micro\_X.sh

   * **Manually (from the micro\_X directory):**  
     source .venv/bin/activate  
     python3 main.py

   * **macOS Alias:** If you set up an alias (e.g., microx), use that.

### **Interacting with micro\_X**

* **Direct Commands:** Type any Linux command and press Enter.  
  (\~) \> ls \-l

* **AI Translation:** Prefix your query with /ai.  
  (\~) \> /ai list all python files in my documents folder

* **Command Management:** Use /command help to see how to add, remove, list, or move categorized commands.  
  (\~) \> /command list  
  (\~) \> /command add "my\_custom\_script.sh \--interactive" interactive\_tui

* **Navigation & Control:**  
  * Ctrl+C / Ctrl+D: Exit micro\_X or cancel current categorization prompt.  
  * Enter: Submit command/query.  
  * Up/Down Arrows: Navigate command history / input lines.  
  * Tab: Attempt completion / indent.  
  * PgUp/PgDn: Scroll output area.

## **Configuration**

* **Ollama Models:** Model names for translation and validation are defined as constants at the top of main.py.  
* **Command Categories:** Stored in config/command\_categories.json within the micro\_X directory.  
* **Command History:** Stored in .micro\_x\_history.  
* **Logs:** logs/micro\_x.log.  
* **Tmux Configuration (Optional):** The micro\_X.sh script references config/.tmux.conf. You can customize this for your micro\_X tmux sessions.  
* **OLLAMA\_HOST (for WSL):** Refer to setup\_micro\_x\_wsl.md for configuring this environment variable if running Ollama on the Windows host and micro\_X in WSL.

## **Future Ideas & Contributions**

* Enhanced parsing for AI output.  
* More sophisticated security sandboxing.  
* User-configurable AI parameters (temperature, etc.).  
* Support for more advanced tmux integrations.  
* Plugin system for extending functionality.

Contributions, bug reports, and feature requests are welcome\! Please open an issue or pull request on the [GitHub repository](https://github.com/thurtz/micro_X.git).

*This README was drafted with the assistance of an AI.*