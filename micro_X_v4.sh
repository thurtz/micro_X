#!/bin/bash

# micro_X V4 Launcher (Config-Driven Edition)
# ------------------

# Navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Check for virtual environment
if [ ! -f ".venv/bin/activate" ]; then
    echo "ERROR: Virtual environment '.venv' not found."
    echo "Please run ./setup.sh first."
    exit 1
fi

# Determine Tmux Session Name
SESSION_NAME="micro_x_v4"
if command -v git >/dev/null 2>&1 && [ -d ".git" ]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null | sed 's/\//_/g')
    SESSION_NAME="micro_x_v4_${BRANCH}"
fi

# Check for tmux
if ! command -v tmux >/dev/null 2>&1; then
    echo "ERROR: tmux is not installed. V4 requires tmux."
    exit 1
fi

# Launch
TMUX_CONFIG="$SCRIPT_DIR/config/.tmux_v4.conf"
LAUNCH_CMD="bash -c 'source .venv/bin/activate && python3 -m micro_X_v4'"

echo "🚀 Launching micro_X V4 in tmux session: $SESSION_NAME"

if [ -n "$TMUX" ]; then
    # We are inside tmux, create the session and switch to it
    tmux -f "$TMUX_CONFIG" new-session -d -s "$SESSION_NAME" "$LAUNCH_CMD" 2>/dev/null
    # Ensure new windows also use this command
    tmux set-option -t "$SESSION_NAME" default-command "$LAUNCH_CMD"
    tmux switch-client -t "$SESSION_NAME"
else
    # We are not in tmux, create and attach
    tmux -f "$TMUX_CONFIG" new-session -d -s "$SESSION_NAME" "$LAUNCH_CMD"
    # Ensure new windows also use this command
    tmux set-option -t "$SESSION_NAME" default-command "$LAUNCH_CMD"
    tmux attach-session -t "$SESSION_NAME"
fi
