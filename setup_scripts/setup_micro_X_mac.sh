#!/bin/bash

# Script to set up the micro_X environment on macOS
# MODIFIED to be called from a root setup.sh and accept PROJECT_ROOT

echo "--- micro_X Setup Script for macOS (OS-Specific) ---"
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

# --- 1. Install Homebrew (if not installed) ---
echo "--- Checking for Homebrew ---"
if ! command_exists brew; then
    echo "Homebrew not found. Attempting to install Homebrew..."
    echo "Please follow the instructions from the official Homebrew installation script."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    if ! command_exists brew; then
        echo "ERROR: Homebrew installation failed or was not completed."
        echo "Please install Homebrew manually from https://brew.sh/ and re-run this script."
        exit 1
    fi
    echo "Homebrew installed successfully."
    # Attempt to add Homebrew to PATH for the current session
    if [ -x "/opt/homebrew/bin/brew" ]; then # Apple Silicon
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x "/usr/local/bin/brew" ]; then # Intel Macs
        eval "$(/usr/local/bin/brew shellenv)"
    fi
else
    echo "Homebrew is already installed."
fi
echo ""

# --- 2. Install Prerequisites using Homebrew ---
echo "--- Installing/Checking Prerequisites via Homebrew ---"

# Python 3
echo "Checking for Homebrew Python 3..."
if ! command_exists python3 || ! (python3 --version 2>&1 | grep -q "Python 3\.[8-9]\|Python 3\.1[0-9]"); then
    echo "A suitable Homebrew Python 3 (3.8+) not found or system Python is default. Attempting to install/upgrade..."
    brew install python
    if ! command_exists python3 || ! (python3 --version 2>&1 | grep -q "Python 3\.[8-9]\|Python 3\.1[0-9]"); then
        echo "ERROR: Failed to install Homebrew Python 3."
        echo "Please ensure Homebrew Python (3.8+) is installed and in your PATH."
        exit 1
    fi
    echo "Homebrew Python 3 installed/updated."
else
    echo "Homebrew Python 3 ($(python3 --version)) seems to be installed."
fi
# Ensure pip is available for the Homebrew python
if ! python3 -m pip --version >/dev/null 2>&1; then
    echo "pip for Homebrew Python3 not found. This is unusual. Please check your Python installation."
    exit 1
fi

# tmux
echo "Checking for tmux..."
if ! command_exists tmux; then
    echo "tmux not found. Attempting to install via Homebrew..."
    brew install tmux
    if ! command_exists tmux; then
        echo "ERROR: Failed to install tmux. Please install it manually ('brew install tmux') and re-run this script."
        exit 1
    fi
    echo "tmux installed."
else
    echo "tmux is already installed."
fi
echo ""

# --- 3. Ollama Setup ---
echo "--- Ollama Setup ---"
if ! command_exists ollama; then
    echo "Ollama command not found."
    echo "Please download and install the Ollama macOS application from https://ollama.com/"
    echo "After installation, ensure the Ollama application is running."
    read -p "Have you installed and started the Ollama macOS application? (y/N) " ollama_installed_choice
    if [[ ! "$ollama_installed_choice" =~ ^[Yy]$ ]]; then
        echo "Ollama installation was skipped or not confirmed. micro_X requires Ollama to function."
        exit 1
    elif ! command_exists ollama; then
        echo "Ollama command still not found. Please ensure it's in your PATH (usually added by the installer) and the app is running."
        exit 1
    else
        echo "Ollama confirmed by user. Make sure the Ollama application is running."
    fi
else
    echo "Ollama command is available. Ensure the Ollama application is running."
fi
echo ""

# --- 4. Install Required Ollama Models ---
echo "--- Installing Ollama Models (Requires Ollama application to be running) ---"
if command_exists ollama; then
    MODELS=(
        "vitali87/shell-commands-qwen2-1.5b-q8_0-extended"
        "vitali87/shell-commands-qwen2-1.5b-extended"
        "herawen/lisa"
    )
    echo "Note: Pulling models can take a significant amount of time and storage."
    read -p "Do you want to proceed with pulling these models now? (y/N) " pull_models_choice
    if [[ "$pull_models_choice" =~ ^[Yy]$ ]]; then
        for model in "${MODELS[@]}"; do
            echo "Pulling Ollama model: $model ..."
            ollama pull "$model"
            if ollama list | grep -q "${model%%:*}"; then
                echo "$model pulled successfully or already exists."
            else
                echo "WARNING: Failed to pull $model or could not verify. Please check manually. Ensure the Ollama application is running."
            fi
        done
    else
        echo "Skipping Ollama model pulling. You will need to pull them manually later for micro_X to function."
    fi
else
    echo "Skipping Ollama model installation because Ollama command was not found."
fi
echo ""

# --- 5. Setting up micro_X Python Environment ---
echo "--- Setting up Python Environment for micro_X ---"

# Check if main.py exists in the PROJECT_ROOT
if [ ! -f "$PROJECT_ROOT/main.py" ]; then # MODIFIED
    echo "ERROR: main.py not found in the project root ($PROJECT_ROOT)."
    echo "Please ensure the main setup.sh script is run from the correct project root."
    exit 1
fi

# Create a Virtual Environment in PROJECT_ROOT
VENV_DIR="$PROJECT_ROOT/.venv" # MODIFIED
if [ -d "$VENV_DIR" ]; then
    echo "Python virtual environment '$VENV_DIR' already exists. Skipping creation."
else
    echo "Creating Python virtual environment in '$VENV_DIR' using $(python3 --version)..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment."
        exit 1
    fi
    echo "Virtual environment created."
fi

# Create requirements.txt if it doesn't exist in PROJECT_ROOT
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt" # MODIFIED
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "Creating $REQUIREMENTS_FILE..."
    cat <<EOF > "$REQUIREMENTS_FILE"
# Python dependencies for micro_X

prompt_toolkit>=3.0.0
ollama>=0.1.0
EOF
    echo "$REQUIREMENTS_FILE created."
else
    echo "$REQUIREMENTS_FILE already exists."
fi

# Install Python Dependencies into the virtual environment
echo "Installing Python dependencies from $REQUIREMENTS_FILE into $VENV_DIR..."
"$VENV_DIR/bin/python3" -m pip install -r "$REQUIREMENTS_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install Python dependencies."
    echo "Try activating the virtual environment manually ('source $VENV_DIR/bin/activate') and then run 'pip3 install -r $REQUIREMENTS_FILE'."
    exit 1
fi
echo "Python dependencies installed."
echo ""

# --- 6. Make Scripts Executable ---
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

# --- 7. Setup Complete ---
echo "--- Setup Complete for macOS! ---"
echo ""
echo "IMPORTANT NEXT STEPS:"
echo "1. Ensure the Ollama macOS application is running."
echo ""
echo "2. To run micro_X (from the micro_X directory: cd \"$PROJECT_ROOT\"):" # MODIFIED
echo "   If you have micro_X.sh (recommended):"
echo "     ./micro_X.sh"
echo "     (This script should activate the virtual environment and start micro_X in tmux)."
echo ""
echo "   If running main.py directly:"
echo "     source .venv/bin/activate"
echo "     ./main.py  # or python3 main.py"
echo ""
echo "Consider creating a shell alias for easier launching, e.g., in your ~/.zshrc:"
echo "  alias microx='cd \"$PROJECT_ROOT\" && ./micro_X.sh'" # MODIFIED
echo "Then run 'source ~/.zshrc' and you can start micro_X by typing 'microx'."
echo ""
echo "If you skipped model pulling, ensure you pull them with 'ollama pull <model_name>' while the Ollama app is running."
echo "------------------------------------------"

exit 0
