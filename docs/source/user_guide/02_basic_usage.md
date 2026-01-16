# **2. Basic Usage**

This section covers the fundamentals of interacting with the micro_X shell.

## **Launching micro_X**

The recommended way to launch micro_X is by using the provided shell script from within the project directory:  
`./micro_X.sh`

This script correctly handles activating the Python virtual environment and managing the underlying tmux session.  
If you installed the desktop entry during setup on Linux, you can also launch it from your application menu.

## **The Interface (Default Textual UI)**

The micro_X interface is divided into distinct zones:

* **Top Bar (Key Hints)**: A toolbar at the very top displaying clickable shortcuts for common actions (Help, Docs, Quit, etc.).
* **Output Log**: The large central area displays command output, AI messages, and logs. It supports **Markdown rendering** for rich text formatting and wraps text automatically.
* **Interaction Zone**: A dynamic area near the bottom that appears when micro_X needs your input (e.g., confirming an AI suggestion) or to show a live status (e.g., "Thinking...").
* **Command Input**: The bottom-most field where you type commands or queries. It features **real-time syntax highlighting** for shell commands and supports multi-line wrapping.

## **Keybindings**

**Global Shortcuts:**
* **F1**: Show Help.
* **Ctrl+D**: Open Documentation in your browser.
* **Ctrl+R**: Search Command History (Interactive Filter).
* **Ctrl+T**: Spawn a new raw shell session (bash) in a new tmux window.
* **Ctrl+L**: Clear the output log.
* **Ctrl+C**: Cancel the current action or clear the input line.
* **Ctrl+Q**: Quit micro_X.

**Input & Navigation:**
* **Enter**: Submit command.
* **Up / Down Arrows**: Navigate command history.
* **Shift + Select**: Select text in the output log (bypass mouse capture) for copying.
* **Ctrl + Shift + C**: Copy selected text (standard Linux terminal).
* **Ctrl + Shift + V**: Paste text.

## **Executing Standard Linux Commands**

Simply type any Linux command (e.g., `ls -l`, `echo "hello world"`, `git status`) and press **Enter**. The output will appear in the scrollable log area.
