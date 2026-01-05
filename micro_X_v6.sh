#!/bin/bash

# micro_X V6 Launcher (Remote Ollama Fix Edition)
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
SESSION_NAME="micro_x_v6"
if command -v git >/dev/null 2>&1 && [ -d ".git" ]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null | sed 's/\//_/g')
    SESSION_NAME="micro_x_v6_${BRANCH}"
fi

# Check for tmux
if ! command -v tmux >/dev/null 2>&1; then
    echo "ERROR: tmux is not installed."
    exit 1
fi

# Launch
TMUX_CONFIG="$SCRIPT_DIR/config/.tmux.conf" # Use standard config
LAUNCH_CMD="bash -c 'source .venv/bin/activate && PYTHONPATH=$SCRIPT_DIR/micro_X_v6 python3 micro_X_v6/main.py'"

echo "🚀 Launching micro_X V6 in tmux session: $SESSION_NAME"

if [ -n "$TMUX" ]; then
    # We are inside tmux, create the session and switch to it
    tmux -f "$TMUX_CONFIG" new-session -d -s "$SESSION_NAME" "$LAUNCH_CMD" 2>/dev/null
    tmux set-option -t "$SESSION_NAME" default-command "$LAUNCH_CMD"
    tmux switch-client -t "$SESSION_NAME"
else
    # We are not in tmux, create and attach
    tmux -f "$TMUX_CONFIG" new-session -d -s "$SESSION_NAME" "$LAUNCH_CMD"
    tmux set-option -t "$SESSION_NAME" default-command "$LAUNCH_CMD"
    tmux attach-session -t "$SESSION_NAME"
fi
