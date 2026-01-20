# modules/messages.py

"""
Centralized store for user-facing messages, prompts, and log strings.
This facilitates consistency, localization, and easier maintenance.
"""

class ShellMessages:
    # Process Management
    NO_ACTIVE_PROCESS = "ℹ️ No active command to kill."
    PROCESS_TERMINATED = "✅ Terminated command: {command}"
    PROCESS_KILLED = "✅ Killed command: {command}"
    KILL_ERROR = "❌ Error killing command: {error}"
    
    # Aliases
    ALIAS_LOAD_ERROR = "⚠️ Could not load {filename}: {error}"
    ALIAS_EXPANDED = "↪️ Alias expanded: '{alias}' -> '{command}'"
    
    # Security
    COMMAND_BLOCKED = "🛡️ Command blocked by security pattern: {command}"
    INVALID_REGEX = "⚠️ Invalid security regex pattern in config: '{pattern}'."
    
    # CD Command
    DIR_CHANGED = "📂 Changed directory to: {path}"
    DIR_NOT_FOUND = "❌ Error: Directory '{target}' (resolved to '{resolved}') does not exist."
    CD_ERROR = "❌ Error processing 'cd' command: {error}"
    
    # Execution
    EMPTY_COMMAND = "⚠️ Empty command cannot be executed."
    SHELL_NOT_FOUND = "❌ Shell (bash) or command not found for: {command}"
    EXECUTION_ERROR = "❌ Error executing '{command}': {error}"
    COMMAND_EXITED = "⚠️ Command '{command}' exited with code {code}."
    
    OUTPUT_HEADER = "Output from '{command}':"
    STDERR_HEADER = "Stderr from '{command}':"
    NO_OUTPUT = "Output from '{command}': (No output)"
    
    # Tmux
    TMUX_NOT_FOUND = "❌ Error: tmux not found. Cannot execute command in tmux."
    TMUX_LAUNCH_ERROR = "❌ Error launching semi-interactive tmux session '{window}'."
    TMUX_LAUNCH_WAIT = "⚡ Launched semi-interactive command in tmux (window: {window}). Waiting for output..."
    TMUX_LAUNCH_INTERACTIVE = "⚡ Launching interactive command in tmux (window: {window}). micro_X will wait..."
    TMUX_POLL_TIMEOUT = "⚠️ Tmux window '{window}' poll timed out."
    TMUX_SESSION_ENDED = "✅ Interactive tmux session for '{command}' ended."
    TMUX_SESSION_ERROR = "❌ Error or non-zero exit in tmux session '{window}': exited with code {code}"
    TMUX_UNEXPECTED_ERROR = "❌ Unexpected error during tmux execution: {error}"
    
    # TUI Detection
    TUI_DETECTED_TIP = "💡 Tip: Try: /command move \"{command}\" interactive_tui"
    
    # Scripts
    SCRIPT_USAGE = "ℹ️ Usage: /{command} <script_name> [args... | help] | list"
    SCRIPT_NOT_FOUND = "❌ Script not found: {script}.py in '{dir}'."
    SCRIPT_EXEC_LOG = "🚀 Executing script: {command}"
    SCRIPT_COMPLETED = "✅ Script '{script}.py' completed."
    SCRIPT_EXITED = "⚠️ Script '{script}.py' exited with code {code}."
    SCRIPT_ERROR = "❌ Failed to execute script: {error}"
    
    # Built-ins
    EXITING = "Exiting micro_X Shell 🚪"
    UNKNOWN_COMMAND_PREFIX = "❌ Unknown command: {command}"
    EMPTY_BANG_COMMAND = "❌ Empty command after '!' prefix."
    UNKNOWN_BANG_COMMAND = "✨ '{command}' is not a known command. Starting categorization..."
    
    # AI
    OLLAMA_UNAVAILABLE = "⚠️ Ollama service is not available."
    AI_QUERY_EMPTY = "⚠️ AI query empty."
    AI_QUERY_LOG = "🤖 AI Query: {query}"
    AI_NO_VALID_COMMAND = "🤔 AI could not produce a validated command."
    ROUTER_CHECK = "✨ '{command}' is not a known command. Checking with Router AI..."
    TRANSLATOR_FALLBACK = "🤔 Router found no tool. Trying with Translator AI..."
    TRANSLATION_FAILED = "🤔 AI translation failed. Trying original input as a direct command."
