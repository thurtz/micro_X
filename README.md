# **micro_X: The AI-Enhanced Shell**

micro_X is an intelligent, interactive shell environment designed to bridge the gap between natural language and executable Linux commands. It leverages local large language models (LLMs) via Ollama to translate your queries, validate commands, explain their functionality, and streamline your command-line workflow. It also features branch-aware integrity checks to ensure code reliability when running on stable or testing branches.

GitHub Repository: https://github.com/thurtz/micro_X.git
Detailed User Guide: docs/user_guide/index.md
Changelog: CHANGELOG.md

## **Quick Start / Installation**

### **Option 1: Docker (Recommended for Stability)**

The fastest way to get a perfectly stable environment is using Docker.

1.  **Run the Docker Wrapper:**
    ```bash
    ./docker-micro_X.sh
    ```
    *   This will build a Debian Trixie image with all dependencies (Python 3.13, Git, GitHub CLI) pre-installed.
    *   **Host Control:** Use the `!` prefix (e.g., `!apt update`) to execute commands directly on your host system from within the container.

### **Option 2: Native Setup**

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/thurtz/micro_X.git
    cd micro_X
    ```
2.  **Run the Unified Setup Script:**
    ```bash
    ./setup.sh
    ```
    *   The script will guide you through installing dependencies and setting up the Python environment.

## **Overview**

micro_X provides a modern text-based user interface (TUI) where you can:

*   Type standard Linux commands with **syntax highlighting** in the input field.
*   Enter natural language queries and have them automatically translated into shell commands.
*   **Host Access from Docker:** When running in a container, all standard commands and AI-generated commands execute on the host by default.
*   **Manual Shell Escape (`!`):** Prefix any command with `!` to force it to run natively on your host system.
*   **Query Documentation:** Ask questions about the project's documentation in natural language using the `/docs --query` command.
*   **Web-Based Configuration Manager:** An integrated tool to easily view and edit user configurations and command categorizations via a web interface (launched with the `/config --start` command).
*   **Clone-Based Development Workflow:** Use the `/clone --bump` utility to create isolated development environments (Git worktrees) for safe testing and refactoring.

## **Key Features**

*   **AI-Powered Command Generation & Validation:** Natural language translation, validation, and explanation powered by local Ollama models.
*   **Dockerized Distribution:** Run in a guaranteed Debian environment while maintaining complete system control.
*   **Modern TUI Experience:** Interactive top bar, syntax highlighting, and rich Markdown rendering.
*   **Command Categorization:** Handles `simple`, `semi_interactive`, and `interactive_tui` commands with intelligent tmux integration.
*   **Multi-Layered Security:** Configurable deny-lists, warn-lists, and a mandatory user confirmation flow for all AI actions.

## **Usage**

1.  **Launch micro_X:** `./micro_X.sh` (Native) or `./docker-micro_X.sh` (Docker).
2.  **Direct Commands:** Type any Linux command (e.g., `ls -l`).
3.  **AI Translation:** Type a query (e.g., `find my large videos`).
4.  **Host Breakout (Docker only):** Prefix with `!` to escape the container (e.g., `!reboot`).

---
This README was updated to reflect the v0.0.1059 Dockerized deployment architecture.
