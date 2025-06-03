#!/bin/bash

# Navigate to the directory where this script is located
# This ensures that .venv and main.py are found correctly relative to the script.
SCRIPT_DIR_INNER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR_INNER" || { echo "ERROR: Could not navigate to script directory: $SCRIPT_DIR_INNER"; exit 1; }

# Activate the virtual environment
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
else
    echo "ERROR: Virtual environment '.venv' not found or activate script missing in $SCRIPT_DIR_INNER."
    echo "Please run the setup script first."
    exit 1
fi

# --- Determine Tmux Session Name Based on Git Branch ---
DEFAULT_SESSION_NAME="micro_x_app" # A more generic default if not a git repo or branch detection fails
SESSION_NAME="$DEFAULT_SESSION_NAME"
BRANCH_NAME_SANITIZED=""

if command -v git >/dev/null 2>&1 && [ -d ".git" ]; then
    # Attempt to get current branch name
    BRANCH_OUTPUT=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$BRANCH_OUTPUT" ] && [ "$BRANCH_OUTPUT" != "HEAD" ]; then
        # Sanitize branch name: replace slashes with underscores, remove other non-alphanumeric characters except hyphen
        BRANCH_NAME_SANITIZED=$(echo "$BRANCH_OUTPUT" | sed 's/\//_/g' | sed 's/[^a-zA-Z0-9_-]//g')
        if [ -n "$BRANCH_NAME_SANITIZED" ]; then
            SESSION_NAME="micro_x_${BRANCH_NAME_SANITIZED}"
        fi
    elif [ "$BRANCH_OUTPUT" == "HEAD" ]; then # Detached HEAD state
        # Use a short commit hash for uniqueness if possible, otherwise a generic detached name
        COMMIT_HASH_SHORT=$(git rev-parse --short HEAD 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$COMMIT_HASH_SHORT" ]; then
            SESSION_NAME="micro_x_detached_${COMMIT_HASH_SHORT}"
        else
            SESSION_NAME="micro_x_detached"
        fi
    fi
    echo "INFO: Detected Git branch context. Using tmux session name: $SESSION_NAME"
else
    echo "INFO: Not a Git repository or 'git' command not found. Using default tmux session name: $SESSION_NAME"
fi
# --- End Tmux Session Name Determination ---

# Check if tmux is installed
if ! command -v tmux >/dev/null 2>&1; then
    echo "ERROR: tmux is not installed. micro_X requires tmux to run."
    echo "Please install tmux (e.g., 'sudo apt install tmux' or 'brew install tmux') and try again."
    exit 1
fi

# Check if config/.tmux.conf exists
TMUX_CONFIG_FILE="config/.tmux.conf"
if [ ! -f "$TMUX_CONFIG_FILE" ]; then
    echo "ERROR: Tmux configuration file '$TMUX_CONFIG_FILE' not found in $SCRIPT_DIR_INNER."
    echo "Please ensure the project structure is correct."
    exit 1
fi

# Start or attach to the tmux session running micro_X
# The -f flag specifies the config file.
# new-session -A: creates a new session if one with the name doesn't exist, otherwise attaches.
# -s $SESSION_NAME: specifies the session name.
echo "Launching micro_X in tmux session: $SESSION_NAME (using config: $TMUX_CONFIG_FILE)"
tmux -f "$TMUX_CONFIG_FILE" new-session -A -s "$SESSION_NAME"

# Optional: If you want to automatically open a new window in the SAME session to tail logs:
# This would require the main session ($SESSION_NAME) to be already running or just created.
# This line is commented out by default.
# if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
#   tmux new-window -t "$SESSION_NAME:" -n "micro_x_logs" "tail -f logs/micro_x.log"
# fi
