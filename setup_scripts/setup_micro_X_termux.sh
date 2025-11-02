#!/bin/bash

# Script to set up the micro_X environment on Termux (Android)
# MODIFIED to be called from a root setup.sh and accept PROJECT_ROOT
# MODIFIED to use Poetry for dependency management

echo "--- micro_X Setup Script for Termux (OS-Specific) ---"
echo ""

# --- Accept PROJECT_ROOT as the first argument ---
if [ -z "$1" ]; then
    echo "ERROR: This script expects PROJECT_ROOT as its first argument."
    echo "Please run it via the main setup.sh script in the project root."
    exit 1
fi
PROJECT_ROOT="$1"
echo "Using Project Root: $PROJECT_ROOT"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- 1. Update Termux & Install Prerequisites ---
echo "--- Updating Termux packages and Installing Prerequisites ---"
pkg update -y && pkg upgrade -y

echo "Installing/checking core packages (python, tmux, git)..."
CORE_PACKAGES="python tmux git"
for pkg_name in $CORE_PACKAGES; do
    if ! command_exists "$pkg_name"; then
        echo "Installing $pkg_name..."
        pkg install "$pkg_name" -y
        if ! command_exists "$pkg_name"; then
            echo "ERROR: Failed to install $pkg_name. Please try installing it manually ('pkg install $pkg_name') and re-run this script."
            exit 1
        fi
    else
        echo "$pkg_name is already installed."
    fi
done
echo "Core packages checked/installed."
echo ""

# --- 2. Ollama Setup ---
echo "--- Ollama Setup ---"
if ! command_exists ollama; then
    echo "Ollama command not found."
    echo "Attempting to guide Ollama installation for Termux (ARM64)..."
    echo "Please follow these steps manually if the automated attempt fails or if you have a different architecture."
    echo ""
    echo "1. Visit https://github.com/ollama/ollama/releases and find the latest release."
    echo "2. Look for a Linux ARM64 binary (e.g., 'ollama-linux-arm64')."
    echo "3. Download it. You can use 'curl -Lo ollama-linux-arm64 <URL_FROM_RELEASES>' in Termux."
    echo "   Example (replace with actual latest URL):"
    echo "   curl -Lo ollama-linux-arm64 https://github.com/ollama/ollama/releases/download/v0.1.30/ollama-linux-arm64" # Replace with actual latest
    echo ""
    echo "4. Make it executable: chmod +x ollama-linux-arm64"
    echo "5. Move it to your bin directory: mv ollama-linux-arm64 $PREFIX/bin/ollama"
    echo ""
    read -p "Have you completed these steps and installed Ollama? (y/N) " ollama_installed_choice
    if [[ ! "$ollama_installed_choice" =~ ^[Yy]$ ]]; then
        echo "Ollama installation was skipped or not confirmed. micro_X requires Ollama to function."
        echo "Please install Ollama and then re-run this script or manually pull the models."
        # Exit if Ollama is critical and not confirmed
        # exit 1
    elif ! command_exists ollama; then
        echo "Ollama command still not found after manual installation steps. Please verify your installation."
        exit 1
    else
        echo "Ollama confirmed to be installed by user."
    fi
else
    echo "Ollama command is already available."
fi

if command_exists ollama; then
    echo "To use Ollama, you typically need to run 'ollama serve' in a separate Termux session."
    echo "You can do this by opening a new Termux session and running 'ollama serve'."
    echo "Alternatively, to run it in the background in the current session (less reliable for long use): 'nohup ollama serve > ollama.log 2>&1 &'"
    echo ""
    read -p "Is the Ollama server running now (e.g., in another session)? (y/N) " ollama_running_choice
    if [[ ! "$ollama_running_choice" =~ ^[Yy]$ ]]; then
        echo "Ollama server not confirmed as running. Model pulling might fail."
        echo "Please ensure 'ollama serve' is active before proceeding with model downloads or running micro_X."
    else
        echo "Verifying connection to Ollama server..."
        if ! curl --fail --silent --show-error http://localhost:11434/ >/dev/null 2>&1; then
            echo "ERROR: Could not connect to Ollama server at http://localhost:11434/"
            echo "Please ensure 'ollama serve' is running correctly in another Termux session."
            exit 1
        fi
        echo "Successfully connected to Ollama server."
    fi
else
    echo "Ollama command not found. Cannot proceed with model downloads or verify server status."
fi
echo ""

# --- 3. Install Required Ollama Models ---
echo "--- Installing Ollama Models (Requires Ollama server to be running) ---"
if command_exists ollama; then
required_models=(
    "vitali87/shell-commands-qwen2-1.5b-q8_0-extended"
    "herawen/lisa"
    "nomic-embed-text"
    "qwen3:0.6b"
)
for model in "${required_models[@]}"; do
            echo "Pulling Ollama model: $model ..."
            ollama pull "$model"
            # Basic check
            if ollama list | grep -q "${model%%:*}"; then
                echo "$model pulled successfully or already exists."
            else
                echo "WARNING: Failed to pull $model or could not verify. Please check manually. Ensure 'ollama serve' is running."
            fi
        done
    else
        echo "Skipping Ollama model pulling. You will need to pull them manually later for micro_X to function."
    fi
else
    echo "Skipping Ollama model installation because Ollama command was not found."
fi
echo ""

# --- 4. Setting up micro_X Python Environment with Poetry ---
echo "--- Setting up Python Environment for micro_X with Poetry ---"

# Install Poetry
if ! command_exists poetry; then
    echo "Poetry not found. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python -
    # Add poetry to path for the current session
    export PATH="$HOME/.local/bin:$PATH"
    if ! command_exists poetry; then
        echo "ERROR: Poetry installation failed. Please install it manually and re-run this script."
        echo "You might need to restart your shell or add $HOME/.local/bin to your PATH."
        exit 1
    fi
    echo "Poetry installed."
else
    echo "Poetry is already installed."
fi

if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
    echo "ERROR: pyproject.toml not found in the project root ($PROJECT_ROOT)."
    exit 1
fi

echo "Configuring Poetry to create the virtual environment in the project directory..."
poetry config virtualenvs.in-project true

echo "Installing Python dependencies with Poetry..."
poetry install --no-root
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install Python dependencies with Poetry."
    exit 1
fi
echo "Python dependencies installed."
echo ""

# --- 5. Make Scripts Executable ---
echo "--- Making Scripts Executable ---"
if [ -f "$PROJECT_ROOT/main.py" ]; then # MODIFIED
    chmod +x "$PROJECT_ROOT/main.py" # MODIFIED
    echo "main.py is now executable."
fi

MICRO_X_LAUNCHER_SH="$PROJECT_ROOT/micro_X.sh" # MODIFIED
if [ -f "$MICRO_X_LAUNCHER_SH" ]; then
    chmod +x "$MICRO_X_LAUNCHER_SH"
    echo "micro_X.sh is now executable."
else
    echo "INFO: micro_X.sh (launch script) not found. This script is recommended for running micro_X."
fi
echo ""

# --- 6. Setup Complete ---
echo "--- Setup Complete for Termux! ---"
echo ""
echo "IMPORTANT NEXT STEPS:"
echo "1. Ensure the Ollama server is running. Open a NEW TERMUX SESSION and run:"
echo "   ollama serve"
echo "   Keep this session open while you use micro_X."
echo ""
echo "2. To run micro_X (in your original or another new Termux session):"
echo "   a. Navigate to the micro_X directory:"
echo "     cd \"$PROJECT_ROOT\"" # MODIFIED
echo "   b. If you have micro_X.sh, run it:"
echo "     ./micro_X.sh"
echo "     (This script should activate the virtual environment and start micro_X in tmux)."
echo ""
echo "   c. If running main.py directly (and micro_X.sh doesn't exist or you prefer manual):"
echo "     poetry shell"
echo "     python main.py"
echo ""
echo "If you skipped model pulling, ensure you pull them with 'ollama pull <model_name>' while 'ollama serve' is active."
echo "------------------------------------------"

exit 0