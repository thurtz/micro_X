## **micro\_X User Guide**

Welcome to the micro\_X User Guide\! This document provides detailed information on using micro\_X, including its AI features, command categorization, command confirmation, Ollama service management, and interaction with tmux for certain command types.

### **1\. Introduction to micro\_X**

micro\_X is an AI-enhanced shell designed to make your command-line experience more intuitive and powerful. It allows you to:

* Execute standard Linux commands.  
* Translate natural language queries into commands using /ai.  
* Benefit from AI-powered validation of commands.  
* Review, get AI explanations for, modify, or cancel AI-generated commands before execution.  
* Categorize commands for optimal execution, especially for interactive or long-running tasks which are handled via tmux.  
* Manage the Ollama service directly from within micro\_X.

### **2\. Getting Started**

* **Installation and Setup:** Before using micro\_X, ensure it has been properly installed and configured. Please refer to the main README.md file in the project root or run the ./setup.sh script (also in the project root) for detailed setup instructions tailored to your operating system.  
* **Launching micro\_X:**  
  * Recommended Method (./micro\_X.sh):  
    From the terminal, navigate to the micro\_X directory and run ./micro\_X.sh. This script is the preferred way to launch micro\_X as it:  
    1. Activates the Python virtual environment.  
    2. Starts micro\_X (i.e., main.py) *inside a dedicated tmux session* (usually named micro\_X). This provides the most integrated experience.  
  * **Desktop Shortcut (Linux Mint):** If you used the setup script and installed the desktop entry, clicking "micro\_X" in your application menu will typically run the micro\_X.sh script.  
  * Manual Method (python3 main.py):  
    You can run micro\_X directly by navigating to its directory, activating the virtual environment (source .venv/bin/activate), and then running python3 main.py.  
    Note on tmux features with manual launch: If you launch main.py directly, micro\_X itself will not be running inside a tmux session. However, commands categorized as semi\_interactive or interactive\_tui will still attempt to launch in new, independent tmux windows/sessions.  
* **Ensuring Ollama is Ready:** Before using AI features, ensure Ollama is running. You can check this within micro\_X using the /ollama status command (see section 4.5).  
* **The Interface:**  
  * **Output Area:** The top, larger pane displays command output, AI messages, and logs. It's scrollable.  
  * **Input Area:** The bottom pane with a prompt (e.g., (\~) \>) is where you type your commands or /ai queries.  
  * **Key Help Bar:** A single line at the very bottom shows common keybindings.

### **3\. micro\_X Keybindings**

micro\_X uses several keybindings for efficient operation:

* **Enter**: Submits the current command or query in the input field.  
* **Ctrl+C / Ctrl+D**:  
  * In normal input mode: Exits micro\_X.  
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

### **4\. Core micro\_X Usage**

#### **4.1. Executing Standard Linux Commands**

Simply type any Linux command (e.g., ls \-l, echo "hello world", git status) and press Enter. The output will appear in the output area.

#### **4.2. Using AI Translation (/ai command) & Command Confirmation**

To translate a natural language query into a command:

1. Type /ai followed by your query.  
   * Example: /ai show me all files larger than 10MB in the current directory  
   * Example: /ai what is my current IP address  
2. Press Enter.  
3. micro\_X will:  
   * Send your query to the configured AI translator(s).  
   * The translated command will be validated by another AI model.  
   * You'll see messages like "🤖 AI Query: ...", "🧠 Thinking...", "🤖 AI Suggests (validated): ...".  
4. **Command Confirmation Flow:** If the AI successfully generates and validates a command, you will be prompted to confirm its execution:  
   🤖 AI proposed command (from: /ai your query \-\> suggested\_command):  
       👉 suggested\_command  
   Action: \[Y\]es (Exec, prompt if new) | \[Ys\] Simple & Run | \[Ym\] Semi-Interactive & Run | \[Yi\] TUI & Run | \[E\]xplain | \[M\]odify | \[C\]ancel?  
   \[Confirm AI Cmd\] Choice (Y/Ys/Ym/Yi/E/M/C):

   Your options are:  
   * **Y or yes**: Execute the command. If the command is unknown to micro\_X's categorization system, you will be prompted to categorize it next (see section 4.3).  
   * **Ys**: Execute the command AND categorize it as simple.  
   * **Ym**: Execute the command AND categorize it as semi\_interactive.  
   * **Yi**: Execute the command AND categorize it as interactive\_tui.  
   * **E or explain**: Ask the AI to explain what the suggested\_command does. After the explanation, you will be prompted again to execute, modify, or cancel.  
     🧠 Asking AI to explain: suggested\_command  
     💡 AI Explanation:  
     The command 'suggested\_command' does XYZ...  
     Command to consider: suggested\_command  
     Action: \[Y\]es (Exec, prompt if new) | \[Ys\] Simple & Run | \[Ym\] Semi-Interactive & Run | \[Yi\] TUI & Run | \[M\]odify | \[C\]ancel?  
     \[Confirm AI Cmd\] Choice (Y/Ys/Ym/Yi/M/C):

   * **M or modify**: The suggested\_command will be loaded into your input field, allowing you to edit it before pressing Enter to submit the modified version.  
   * **C or cancel (or N or no)**: Abort the execution. The command will not run.

#### **4.3. Command Categorization (for unknown direct commands or AI commands confirmed with 'Y')**

When micro\_X encounters a command it hasn't seen before (either typed directly, or an AI-generated command confirmed with a simple 'Y' that isn't yet categorized), it will prompt you to categorize it. This helps micro\_X run the command appropriately.

* **Categories:**  
  * **simple**: For commands that run quickly, produce non-interactive output, and don't require a persistent terminal session (e.g., ls, echo, cat somefile.txt). Chained commands like ls \-l | grep .txt are also often suitable here. These are executed directly, and their output is captured in the micro\_X output area.  
  * **semi\_interactive**: For commands that might run for a while, produce a lot of output, or have some minimal interactivity that doesn't require full TUI control (e.g., apt update, a long script, ping google.com). These are run in a new tmux window. Their output is captured and displayed in micro\_X after the command finishes or the tmux window closes/times out.  
    * **Smart Output Handling:** If a semi\_interactive command produces output resembling a full-screen TUI application, micro\_X avoids displaying garbled output and suggests re-categorizing to interactive\_tui.  
  * **interactive\_tui**: For fully interactive terminal applications (e.g., nano, vim, htop, ssh user@host). These are run in a new tmux window that micro\_X effectively hands control to. When you exit the application (and thus the tmux window), you'll return to micro\_X.  
* **Categorization Prompt (Example for a directly typed unknown command):**  
  Command 'my\_new\_script.sh \--verbose' is not categorized. Choose an action:  
    1: simple             (Direct output in micro\_X)  
    2: semi\_interactive   (Output in micro\_X after tmux run (may be interactive))  
    3: interactive\_tui    (Full interactive tmux session)  
    M: Modify command before categorizing  
    D: Execute as default 'semi\_interactive' (once, no save)  
    C: Cancel categorization & execution  
  \[Categorize\] Action (1-3/M/D/C):

  Enter your choice. If you choose 1, 2, or 3, the command and its category will be saved in config/user\_command\_categories.json.

#### **4.4. Managing Command Categories (/command subsystem)**

You can manage your saved command categorizations:

* /command list: Shows all categorized commands (merged view of defaults and user settings).  
* /command add "\<full\_command\_string\>" \<category\_name\_or\_number\>: Adds a new command or updates an existing one.  
  * Example: /command add "htop" interactive\_tui  
  * Example: /command add "my\_backup\_script.sh" 2 (for semi\_interactive)  
* /command remove "\<full\_command\_string\>": Removes a command from your explicit user categorizations. It may then revert to a default category or become unknown.  
* /command move "\<full\_command\_string\>" \<new\_category\_name\_or\_number\>: Moves a command to a different category in your settings.  
* /command run \<cat\_num|cat\_name\> "\<cmd\>": Force runs a command with a specific category for this instance without saving the categorization.  
* /command help: Shows these usage instructions and category descriptions.  
  Remember to quote command strings if they contain spaces.

#### **4.5. Managing the Ollama Service (/ollama command)**

micro\_X provides commands to manage the Ollama service it relies on for AI features:

* /ollama status: Shows the current status of the Ollama executable, API responsiveness, the managed tmux session for ollama serve, and auto-start configuration.  
* /ollama start: Attempts to start the managed ollama serve process in a tmux session if it's not already running and responsive.  
* /ollama stop: Attempts to stop the managed ollama serve tmux session.  
* /ollama restart: Attempts to stop and then restart the managed ollama serve process.  
* /ollama help: Displays help information for these subcommands.

#### **4.6. Chained Commands**

micro\_X supports AI translation and execution of chained commands (e.g., ls \-l | grep .txt && echo "Found").

* When categorized, the entire chained command is treated as a single entity.  
* The "dominant" category usually applies. If any part of a chain requires interactive\_tui (like nano), the whole chain will likely run best under interactive\_tui.

### **5\. Working with tmux (for semi\_interactive and interactive\_tui commands)**

micro\_X uses tmux (a terminal multiplexer) to run commands categorized as semi\_interactive or interactive\_tui.

* **If micro\_X was launched with ./micro\_X.sh (Recommended):**  
  * micro\_X itself runs inside a main tmux session (e.g., named micro\_X).  
  * semi\_interactive and interactive\_tui commands will create *new windows within this main session*. This provides an integrated experience.  
* **If micro\_X was launched with python3 main.py directly:**  
  * micro\_X is not running inside a managed tmux session.  
  * semi\_interactive and interactive\_tui commands will still launch in tmux, but they will typically create *new, independent tmux sessions* (or windows in a default session if a tmux server is already running).

**Behavior of tmux-based commands:**

* **interactive\_tui commands (e.g., nano, htop):**  
  * micro\_X will create a tmux window, and your terminal will switch to show the interactive application.  
  * **Exiting:** To return to micro\_X, exit the application normally (e.g., Ctrl+X in nano). This closes the tmux window, returning you to micro\_X.  
* **semi\_interactive commands (e.g., ping google.com):**  
  * These run in a tmux window, usually in the background relative to your main micro\_X interface.  
  * Output is captured and displayed in micro\_X after completion or timeout.

#### **5.1. Basic tmux Interaction (If you need to manually intervene)**

Knowing tmux basics is helpful. The tmux prefix key is Ctrl+b by default.

* **Listing tmux Sessions & Windows:**  
  * From any terminal (outside tmux or in a different tmux session):  
    tmux ls \# Lists all tmux sessions  
  * If inside a tmux session (e.g., the main micro\_X session when launched with micro\_X.sh):  
    tmux list-windows \# Lists windows in the current session  
  * To list windows in a specific session from outside:  
    tmux list-windows \-t micro\_X \# Replace micro\_X with session name if different  
* Attaching to a tmux Session:  
  If you detached or want to connect to a running session (e.g., the main micro\_X session):  
  tmux attach-session \-t micro\_X \# Or the specific session name  
* Detaching from the Current tmux Session:  
  Leaves the session running in the background.  
  * Press Ctrl+b, release, then press d.  
* **Switching Windows (within a tmux session):**  
  * Ctrl+b then p (previous window)  
  * Ctrl+b then n (next window)  
  * Ctrl+b then \[window\_number\] (e.g., 0, 1\)

#### **5.2. Killing tmux Windows or Panes**

If a command in a tmux window (launched by micro\_X) becomes unresponsive:

1. **Identify the Target:**  
   * For interactive\_tui, you're likely in the problematic window.  
   * For semi\_interactive, you might need to list windows/sessions to find its name (e.g., micro\_x\_xxxx). If micro\_X was launched with micro\_X.sh, switch to the micro\_X tmux session and use tmux list-windows. If launched directly, use tmux ls to find the relevant new session.  
2. **Killing the Current Window/Pane (if you are inside it):**  
   * Try Ctrl+C in the application first.  
   * If that fails: Ctrl+b then x. Confirm with y.  
3. Killing a Specific Window by Name/ID (from within the same tmux server):  
   tmux kill-window \-t \<window\_index\_or\_name\>  
   Example: tmux kill-window \-t micro\_x\_1a2b3c4d

#### **5.3. Handling Processes that Lock Up tmux Windows**

If a process is truly stuck:

1. **Identify PID:** Detach from tmux (Ctrl+b d). Use ps aux | grep \<command\_name\> or htop in a standard terminal to find the PID.  
2. Kill Process:  
   kill \<PID\>  
   \# If necessary:  
   kill \-9 \<PID\> \# Use with caution  
3. **Clean tmux Window:** The tmux window might close or show "Pane is dead." Close it with Ctrl+b x if needed.

### **6\. Security Considerations**

* **AI-Generated Commands:** While micro\_X includes AI validation and a basic command sanitizer, **AI can still generate unexpected or potentially harmful commands.**  
* **Review and Understand:** **Crucially, always use the \[E\]xplain option** in the command confirmation flow (section 4.2) for any AI-generated command if you are unsure about its function or impact.  
* **Modify or Cancel:** Do not hesitate to \[M\]odify commands to your exact needs or \[C\]ancel them if they seem suspicious or incorrect.  
* **User Responsibility:** You are ultimately responsible for the commands executed in your environment. micro\_X is a tool to assist, not a replacement for careful judgment.

### **7\. Troubleshooting Common Issues**

* **"Ollama Connection Error" / AI Features Not Working:**  
  * Ensure the Ollama application/service is running. Use /ollama status within micro\_X.  
  * If the service is not running, try /ollama start.  
  * For WSL: Check OLLAMA\_HOST environment variable and Windows Firewall settings.  
* **AI Translations are Poor:**  
  * Rephrase /ai queries. LLMs are not perfect.  
  * Ensure the correct Ollama models (translator, validator, explainer) are pulled and accessible by Ollama. Check config/default\_config.json for model names.  
* **tmux Errors:** Ensure tmux is installed and accessible in your system's PATH.  
* **Command Categorized Incorrectly:** Use /command move to change a command's category or /command remove to remove your custom categorization (it may then revert to a default or become unknown).

This guide should help you navigate and utilize the features of micro\_X more effectively. Happy shelling\!