# **2. Basic Usage**

This section covers the fundamentals of interacting with the micro_X shell.

## **Launching micro_X**

The recommended way to launch micro_X is by using the provided shell script from within the project directory:  
./micro_X.sh

This script correctly handles activating the Python virtual environment and managing the underlying tmux session.  
If you installed the desktop entry during setup on Linux, you can also launch it from your application menu.

## **The Interface**

The micro_X interface is divided into three main parts:

* **Output Area**: The top, larger pane displays command output, AI messages, and logs. It is scrollable.  
* **Input Area**: The bottom pane with a prompt (e.g., (~) >) is where you type your commands or /ai queries.  
* **Key Help Bar**: A single line at the very bottom shows common keybindings.

## **Keybindings**

* **Enter**: Submits the current command or query.  
* **Ctrl+C / Ctrl+D**: Exits micro_X or cancels an active interactive flow (like categorization or confirmation).  
* **Ctrl+N**: Inserts a newline in the input field for multi-line commands.  
* **Up/Down Arrows**: Navigates through your command history or moves the cursor in a multi-line command.  
* **Tab**: Attempts command completion or inserts 4 spaces.  
* **PageUp / PageDown**: Scrolls the main output area.

## **Executing Standard Linux Commands**

Simply type any Linux command (e.g., ls -l, echo "hello world", git status) and press **Enter**. The output will appear in the output area above the prompt.