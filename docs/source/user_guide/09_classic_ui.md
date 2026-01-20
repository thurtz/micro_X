# **Classic UI (Prompt Toolkit)**

While `textual` is the modern default interface for micro_X, the original `prompt_toolkit` backend remains fully supported. You can switch to it by setting `ui_backend` to `prompt_toolkit` in your `user_config.json`.

## **The Interface**

The classic interface is divided into three main parts:

* **Output Area**: The top, larger pane displays command output, AI messages, and logs.
* **Input Area**: The bottom pane with a prompt (e.g., `(~) >`) is where you type your commands or `/translate` queries.
* **Key Help Bar**: A single line at the very bottom shows common keybindings.

## **Keybindings**

* **Enter**: Submits the current command or query.
* **Ctrl+C / Ctrl+D**: Exits micro_X or cancels an active interactive flow (like categorization or confirmation).
* **Ctrl+N**: Inserts a newline in the input field for multi-line commands.
* **Up/Down Arrows**: Navigates through your command history.
* **Tab**: Attempts command completion.
* **PageUp / PageDown**: Scrolls the main output area.

## **Interactive Flows**

In the classic UI, interactive menus (like command confirmation or categorization) are presented as text-based lists in the output area, requiring you to type a number (1-7) to select an option.
