## micro_X User Guide

Welcome to the micro_X User Guide! This document provides detailed information on using micro_X, including its AI features, command categorization, command confirmation, Ollama service management, interaction with tmux for certain command types, and the new branch-aware developer mode and code integrity checks.

### 1. Introduction to micro_X

micro_X is an AI-enhanced shell designed to make your command-line experience more intuitive and powerful. It allows you to:

* Execute standard Linux commands.
* Translate natural language queries into commands using `/ai`.
* Benefit from AI-powered validation of commands.
* Review, get AI explanations for, modify, or cancel AI-generated commands before execution.
* Categorize commands for optimal execution, especially for interactive or long-running tasks which are handled via tmux.
* Manage the Ollama service directly from within micro_X.
* **Run with confidence:** micro_X performs startup integrity checks on main and testing branches and offers an automatic "Developer Mode" on the dev branch.

### 2. Getting Started

#### 2.1. Choosing a Branch

* **For most users, the `main` branch is recommended.** This branch contains the most stable version of micro_X.
* The `testing` branch is used for features that are being prepared for a stable release. It's generally stable but might have newer, less-tested features.
* The `dev` branch is for active development and may contain experimental features or be unstable at times.

#### 2.2. Installation and Setup

Before using micro_X, ensure it has been properly installed and configured. Please refer to the main `README.md` file in the project root or run the `./setup.sh` script (also in the project root) for detailed setup instructions tailored to your operating system.

* **Important:** For full functionality, including the developer mode and integrity checks, micro_X should be run from a git clone of the repository, and the `git` command must be installed and accessible in your system's PATH.

#### 2.3. Managing Multiple Branch Installations (Optional)

If you wish to work with or test different branches of micro_X simultaneously without them interfering with each other, you can clone the repository into separate directories. This is particularly useful for developers or advanced users.

1.  **Clone for `main` branch (Stable):**
    ```bash
    git clone [https://github.com/thurtz/micro_X.git](https://github.com/thurtz/micro_X.git) micro_X-main
    cd micro_X-main
    # git checkout main # Usually already on main after clone
    ./setup.sh # Run setup within this directory
    ```
2.  **Clone for `testing` branch:**
    ```bash
    git clone [https://github.com/thurtz/micro_X.git](https://github.com/thurtz/micro_X.git) micro_X-testing
    cd micro_X-testing
    git checkout testing
    ./setup.sh # Run setup within this directory
    ```
3.  **Clone for `dev` branch (Development):**
    ```bash
    git clone [https://github.com/thurtz/micro_X.git](https://github.com/thurtz/micro_X.git) micro_X-dev
    cd micro_X-dev
    git checkout dev
    ./setup.sh # Run setup within this directory
    ```
Each of these directories (`micro_X-main`, `micro_X-testing`, `micro_X-dev`) will then be an independent installation with its own virtual environment and configuration (though you might share user-level config if not careful, it's generally best to treat them as separate).

#### 2.4. Launching micro_X

* **Recommended Method (`./micro_X.sh`):**
    From the terminal, navigate to your chosen micro_X directory (e.g., `cd micro_X-main`) and run `./micro_X.sh`. This script is the preferred way to launch micro_X as it:
    1.  Activates the Python virtual environment.
    2.  Starts micro_X (i.e., `main.py`) *inside a dedicated tmux session* (usually named `micro_X`). This provides the most integrated experience.
* **Desktop Shortcut (Linux Mint):** If you used the setup script and installed the desktop entry, clicking "micro_X" in your application menu will typically run the `micro_X.sh` script from the directory it was installed from.
* **Manual Method (`python3 main.py`):** You can run micro_X directly by following these steps:
    1.  Navigate to its directory.
    2.  Activate the virtual environment:
        ```bash
        source .venv/bin/activate
        ```
    3.  Launch a tmux session specific for micro_X (optional, but recommended for full feature parity if not using `micro_X.sh`):
        ```bash
        tmux -f config/.tmux.conf new-session -A -s micro_X
        ```
    4.  Then run `python3 main.py` (from within that tmux session if you started one, or directly if you skipped step 3).

    **Note on tmux features with manual launch outside of the micro_X tmux session:** If you launch `main.py` directly (without step 3, or outside the session started by `micro_X.sh`), micro_X itself will not be running inside a tmux session. However, commands categorized as `semi_interactive` or `interactive_tui` will still attempt to launch in new, independent tmux windows/sessions.

#### 2.5. Startup Behavior (Integrity Checks & Developer Mode)

micro_X checks the current Git branch on startup to determine its operational mode. See section "5. Developer Mode & Code Integrity" for full details.

#### 2.6. Ensuring Ollama is Ready

Before using AI features, ensure Ollama is running. You can check this within micro_X using the `/ollama status` command (see section 4.5).

#### 2.7. The Interface

* **Output Area:** The top, larger pane displays command output, AI messages, and logs. It's scrollable.
* **Input Area:** The bottom pane with a prompt (e.g., `(~) >`) is where you type your commands or `/ai` queries.
* **Key Help Bar:** A single line at the very bottom shows common keybindings.

### 3. micro_X Keybindings

micro_X uses several keybindings for efficient operation:

* **Enter**: Submits the current command or query in the input field.
* **Ctrl+C / Ctrl+D**:
    * In normal input mode: Exits micro_X.
    * During an interactive categorization or **command confirmation** prompt: Cancels the current flow and returns to the normal input prompt.
* **Ctrl+N**: Inserts a newline in the input field.
* **Up Arrow / Down Arrow**:
    * In the input field: Navigates through your command history.
    * If the input field has multiple lines of text: Navigates up/down through those lines.
* **Tab**:
    * Attempts command completion.
    * If no completion is available, inserts 4 spaces for indentation.
* **PageUp / PageDown**: Scrolls the main output area up or down.
* **Ctrl+Up / Ctrl+Down**: Moves the cursor up or down one line within the input field.

### 4. Core micro_X Usage

#### 4.1. Executing Standard Linux Commands

Simply type any Linux command (e.g., `ls -l`, `echo "hello world"`, `git status`) and press Enter. The output will appear in the output area.

#### 4.2. Using AI Translation (`/ai` command) & Command Confirmation

To translate a natural language query into a command:

1.  Type `/ai` followed by your query.
    * Example: `/ai show me all files larger than 10MB in the current directory`
    * Example: `/ai what is my current IP address`
2.  Press Enter.
3.  micro_X will:
    * Send your query to the configured AI translator(s).
    * The translated command will be validated by another AI model.
    * You'll see messages like "🤖 AI Query: ...", "🧠 Thinking...", "🤖 AI Suggests (validated): ...".
4.  **Command Confirmation Flow:** If the AI successfully generates and validates a command, you will be prompted to confirm its execution:
    ```
    🤖 AI proposed command (from: /ai your query -> suggested_command):
    👉 suggested_command
    Action: [Y]es (Exec, prompt if new) | [Ys] Simple & Run | [Ym] Semi-Interactive & Run | [Yi] TUI & Run | [E]xplain | [M]odify | [C]ancel?
    [Confirm AI Cmd] Choice (Y/Ys/Ym/Yi/E/M/C): 
    ```

    Your options are:
    * **Y or yes**: Execute the command. If the command is unknown to micro_X's categorization system, you will be prompted to categorize it next (see section 4.3).
    * **Ys**: Execute the command AND categorize it as `simple`.
    * **Ym**: Execute the command AND categorize it as `semi_interactive`.
    * **Yi**: Execute the command AND categorize it as `interactive_tui`.
    * **E or explain**: Ask the AI to explain what the `suggested_command` does. After the explanation, you will be prompted again to execute, modify, or cancel.
        ```
        🧠 Asking AI to explain: suggested_command
        💡 AI Explanation:
        The command 'suggested_command' does XYZ...
        Command to consider: suggested_command
        Action: [Y]es (Exec, prompt if new) | [Ys] Simple & Run | [Ym] Semi-Interactive & Run | [Yi] TUI & Run | [M]odify | [C]ancel?
        [Confirm AI Cmd] Choice (Y/Ys/Ym/Yi/M/C): 
        ```
    * **M or modify**: The `suggested_command` will be loaded into your input field, allowing you to edit it before pressing Enter to submit the modified version.
    * **C or cancel (or N or no)**: Abort the execution. The command will not run.

#### 4.3. Command Categorization (for unknown direct commands or AI commands confirmed with 'Y')

When micro_X encounters a command it hasn't seen before (either typed directly, or an AI-generated command confirmed with a simple 'Y' that isn't yet categorized), it will prompt you to categorize it. This helps micro_X run the command appropriately.

* **Categories:**
    * **`simple`**: For commands that run quickly, produce non-interactive output, and don't require a persistent terminal session (e.g., `ls`, `echo`, `cat somefile.txt`). Chained commands like `ls -l | grep .txt` are also often suitable here. These are executed directly, and their output is captured in the micro_X output area.
    * **`semi_interactive`**: For commands that might run for a while, produce a lot of output, or have some minimal interactivity that doesn't require full TUI control (e.g., `apt update`, a long script, `ping google.com`). These are run in a new tmux window. Their output is captured and displayed in micro_X after the command finishes or the tmux window closes/times out.
        * **Smart Output Handling:** If a `semi_interactive` command produces output resembling a full-screen TUI application, micro_X avoids displaying garbled output and suggests re-categorizing to `interactive_tui`.
    * **`interactive_tui`**: For fully interactive terminal applications (e.g., `nano`, `vim`, `htop`, `ssh user@host`). These are run in a new tmux window that micro_X effectively hands control to. When you exit the application (and thus the tmux window), you'll return to micro_X.
* **Categorization Prompt (Example for a directly typed unknown command):**
    ```
    Command 'my_new_script.sh --verbose' is not categorized. Choose an action:
    1: simple (Direct output in micro_X)
    2: semi_interactive (Output in micro_X after tmux run (may be interactive))
    3: interactive_tui (Full interactive tmux session)
    M: Modify command before categorizing
    D: Execute as default 'semi_interactive' (once, no save)
    C: Cancel categorization & execution
    [Categorize] Action (1-3/M/D/C): 
    ```
    Enter your choice. If you choose 1, 2, or 3, the command and its category will be saved in `config/user_command_categories.json`.

#### 4.4. Managing Command Categories (`/command` subsystem)

You can manage your saved command categorizations:

* `/command list`: Shows all categorized commands (merged view of defaults and user settings).
* `/command add "<full_command_string>" <category_name_or_number>`: Adds a new command or updates an existing one.
    * Example: `/command add "htop" interactive_tui`
    * Example: `/command add "my_backup_script.sh" 2` (for `semi_interactive`)
* `/command remove "<full_command_string>"`: Removes a command from your explicit user categorizations. It may then revert to a default category or become unknown.
* `/command move "<full_command_string>" <new_category_name_or_number>`: Moves a command to a different category in your settings.
* `/command run <cat_num|cat_name> "<cmd>"`: Force runs a command with a specific category for this instance without saving the categorization.
* `/command help`: Shows these usage instructions and category descriptions.
Remember to quote command strings if they contain spaces.

#### 4.5. Managing the Ollama Service (`/ollama` command)

micro_X provides commands to manage the Ollama service it relies on for AI features:

* `/ollama status`: Shows the current status of the Ollama executable, API responsiveness, the managed tmux session for `ollama serve`, and auto-start configuration.
* `/ollama start`: Attempts to start the managed `ollama serve` process in a tmux session if it's not already running and responsive.
* `/ollama stop`: Attempts to stop the managed `ollama serve` tmux session.
* `/ollama restart`: Attempts to stop and then restart the managed `ollama serve` process.
* `/ollama help`: Displays help information for these subcommands.

#### 4.6. Using Utility Scripts (`/utils` command)

micro_X comes with helpful utility scripts located in the `utils/` directory.

* `/utils list`: Displays a list of available utility scripts.
* `/utils <script_name> [args...]`: Executes the specified utility script.
    * Example: `/utils generate_tree`
    * Example: `/utils generate_snapshot --summary "My snapshot"`
* `/utils <script_name> help` (or **-h**, **--help**): Displays the help message for a specific utility script, showing its available arguments.
    * Example: `/utils generate_snapshot help`

#### 4.7. Chained Commands

micro_X supports AI translation and execution of chained commands (e.g., `ls -l | grep .txt && echo "Found"`).

* When categorized, the entire chained command is treated as a single entity.
* The "dominant" category usually applies. If any part of a chain requires `interactive_tui` (like `nano`), the whole chain will likely run best under `interactive_tui`.

### 5. Developer Mode & Code Integrity

To enhance reliability and security, micro_X implements a branch-aware system for developer mode and code integrity checks.

* **Purpose:** This system aims to ensure that users running micro_X from its stable (`main`) or `testing` branches are using verified and synchronized code. For developers, it provides a seamless experience on the development (`dev`) branch.
* **Developer Mode (`dev` branch):**
    * **Activation:** Automatically activated when micro_X detects it is running from the `dev` Git branch, or if Git context is unavailable (e.g., not a Git repository).
    * **Behavior:** In this mode, startup integrity checks are informational or bypassed. micro_X will run even if there are local uncommitted changes or if the `dev` branch has diverged from its remote counterpart.
    * **Intention:** This mode is designed for active development.
* **Protected Mode (`main` and `testing` branches):**
    * **Activation:** Active when micro_X detects it is running from the `main` or `testing` Git branches.
    * **Integrity Checks Performed at Startup:**
        1.  **Clean Working Directory:** Verifies no uncommitted modifications to tracked files and no untracked files (not ignored by `.gitignore`).
        2.  **Sync with Remote:** Verifies the local branch is synchronized with its remote-tracking branch on `origin`. micro_X attempts to `git fetch` for an up-to-date comparison.
    * **Consequences of Failure:**
        * If critical integrity issues are found (e.g., uncommitted local changes, local branch ahead of or diverged from remote), micro_X will display an error message and **halt execution**. If the UI closes too quickly to read the message, check `logs/micro_x.log` for details.
        * If the local branch is merely *behind* the remote (and `allow_run_if_behind_remote` is true in the configuration, which is the default), a warning will be displayed, and `/update` will be suggested. micro_X will continue to run in this case.
    * **User Action on Failure:** See section "8. Troubleshooting Common Issues".
* **Behavior on Other Branches/States:**
    * **Feature Branches (not `dev`, `main`, `testing`):** Assumes a developer-like mode; integrity checks are informational and do not halt execution.
    * **Detached HEAD State:** Similar to other branches, assumes developer mode.
* **Behavior if Not a Git Repository or `git` is Unavailable:**
    * A warning message will be displayed.
    * Integrity checks will be disabled.
    * micro_X will operate in a mode similar to "Developer Mode."

### 6. Working with tmux (for `semi_interactive` and `interactive_tui` commands)

micro_X uses `tmux` (a terminal multiplexer) to run commands categorized as `semi_interactive` or `interactive_tui`.

* **If micro_X was launched with `./micro_X.sh` (Recommended):**
    * micro_X itself runs inside a main `tmux` session (e.g., named `micro_X`).
    * `semi_interactive` and `interactive_tui` commands will create *new windows within this main session*.
* **If micro_X was launched with `python3 main.py` directly:**
    * `semi_interactive` and `interactive_tui` commands will typically create *new, independent `tmux` sessions*.

**Behavior of `tmux`-based commands:**

* **`interactive_tui` commands (e.g., `nano`, `htop`):**
    * Your terminal will switch to show the interactive application in a new `tmux` window.
    * **Exiting:** Exit the application normally (e.g., `Ctrl+X` in `nano`) to close the `tmux` window and return to micro_X.
* **`semi_interactive` commands (e.g., `ping google.com`):**
    * These run in a `tmux` window, usually in the background.
    * Output is captured and displayed in micro_X after completion or timeout.

#### 6.1. Basic `tmux` Interaction (If you need to manually intervene)

The `tmux` prefix key is `Ctrl+b` by default.

* **Listing `tmux` Sessions & Windows:**
    * From any terminal: `tmux ls` (lists sessions)
    * Inside a `tmux` session: `tmux list-windows` (lists windows in current session)
    * From outside, for a specific session: `tmux list-windows -t micro_X`
* **Attaching to a `tmux` Session:** `tmux attach-session -t micro_X`
* **Detaching from Current `tmux` Session:** `Ctrl+b`, then `d`.
* **Switching Windows (within `tmux`):** `Ctrl+b` then `p` (previous), `n` (next), or a window number (0, 1, ...).

#### 6.2. Killing `tmux` Windows or Panes

If a command in a `tmux` window becomes unresponsive:

1.  **Identify Target:** For `interactive_tui`, you're likely in it. For `semi_interactive`, list windows/sessions to find its name (e.g., `micro_x_xxxx`).
2.  **Kill Current Window/Pane (if inside):** Try `Ctrl+C` in the app. If unresponsive, `Ctrl+b` then `x` (confirm with `y`).
3.  **Kill Specific Window by Name/ID:** `tmux kill-window -t <window_index_or_name>`

#### 6.3. Handling Processes that Lock Up `tmux` Windows

1.  **Identify PID:** Detach from `tmux` (`Ctrl+b d`). Use `ps aux | grep <command_name>` or `htop` in a standard terminal.
2.  **Kill Process:** `kill <PID>` (or `kill -9 <PID>` with caution).
3.  **Clean `tmux` Window:** The `tmux` window might show "Pane is dead." Close it with `Ctrl+b x`.

### 7. Security Considerations

* **AI-Generated Commands:** While micro_X includes AI validation and a basic command sanitizer, **AI can still generate unexpected or potentially harmful commands.**
* **Review and Understand:** **Crucially, always use the `[E]xplain` option** in the command confirmation flow (section 4.2) for any AI-generated command if you are unsure about its function or impact.
* **Modify or Cancel:** Do not hesitate to `[M]odify` commands to your exact needs or `[C]ancel` them if they seem suspicious or incorrect.
* **Startup Integrity Checks:** The checks on `main` and `testing` branches provide an added layer of assurance. When these checks halt the application, it's a signal to review your local repository's state.
* **User Responsibility:** You are ultimately responsible for the commands executed in your environment.

### 8. Troubleshooting Common Issues

* **"Ollama Connection Error" / AI Features Not Working:**
    * Ensure the Ollama application/service is running. Use `/ollama status`.
    * If not running, try `/ollama start`.
    * For WSL: Check `OLLAMA_HOST` environment variable and Windows Firewall.
* **AI Translations are Poor:**
    * Rephrase `/ai` queries.
    * Ensure correct Ollama models are pulled and accessible.
* **`tmux` Errors:** Ensure `tmux` is installed and in PATH.
* **Command Categorized Incorrectly:** Use `/command move` or `/command remove`.
* **micro_X Halts on Startup with "Integrity Check Failed" (on `main` or `testing` branch):**
    * **Message: "Uncommitted local changes or untracked files detected."**
        * *Reason:* You have uncommitted local modifications or new untracked files.
        * *Solution:* Open a standard terminal in your micro_X project directory. Run `git status`. Commit, stash, or discard changes. For development, switch to the `dev` branch (`git checkout dev`).
    * **Message: "Local branch has 'ahead'/'diverged' from 'origin/<branch>'."**
        * *Reason:* Your local branch has commits not on the remote, or both have different new commits. This is considered a state that should be resolved before running on a protected branch.
        * *Solution:* `git fetch origin`. Then, depending on the situation:
            * If **ahead** and changes are intentional for this branch: `git push origin <branchname>`. If not, consider `git reset --hard origin/<branchname>` (DISCARDS LOCAL COMMITS) or move changes to a feature branch.
            * If **diverged**: `git rebase origin/<branchname>` (and resolve conflicts) or `git merge origin/<branchname>`. Or, to discard local changes: `git reset --hard origin/<branchname>`.
            * For development, switch to the `dev` branch.
    * **Message: "Cannot reliably compare with remote. Status: no_upstream/fetch_failed/error."**
        * *Reason & Solution:* Check internet, `git branch -vv` for upstream tracking, `git fetch origin` for errors. Consult `logs/micro_x.log`.
    * **If micro_X closes too quickly to read the error message on startup, always check `logs/micro_x.log` for detailed error information.**
* **micro_X shows warnings about being "behind remote" (on `main` or `testing` branch):**
    * *Reason:* The remote repository has updates that your local branch does not.
    * *Solution:* Run `/update` from within micro_X, or open a standard terminal in the project directory and run `git pull origin <branchname>`. micro_X will typically continue to run in this scenario (if `allow_run_if_behind_remote` is true).

This guide should help you navigate and utilize the features of micro_X more effectively. Happy shelling!
