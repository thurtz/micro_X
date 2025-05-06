#!/bin/bash

# Navigate to micro_X directory
cd "$(dirname "$0")" || exit

# Activate the virtual environment
source .venv/bin/activate

# Start or attach to the tmux session running micro_X
tmux -f config/.tmux.conf new-session -A -s micro_X