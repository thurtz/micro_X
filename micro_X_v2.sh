#!/bin/bash

# micro_X V2 Launcher
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
SESSION_NAME="micro_x_v2"
if command -v git >/dev/null 2>&1 && [ -d ".git" ]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null | sed 's/\//_/g')
    SESSION_NAME="micro_x_v2_${BRANCH}"
fi

# Check for tmux
if ! command -v tmux >/dev/null 2>&1; then
    echo "ERROR: tmux is not installed. V2 requires tmux for interactive features."
    exit 1
fi

# Launch
TMUX_CONFIG="config/.tmux_v2.conf"
echo "🚀 Launching micro_X V2 in tmux session: $SESSION_NAME"
tmux -f "$TMUX_CONFIG" new-session -A -s "$SESSION_NAME"
