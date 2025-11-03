#!/bin/ksh

# Script to set up the micro_X environment on OpenBSD
# This is a "best-effort" script. Ollama must be installed manually.

echo "--- micro_X Setup Script for OpenBSD (OS-Specific) ---"
echo ""
echo "IMPORTANT: This script will attempt to install standard packages using 'doas pkg_add'."
echo "           You may be prompted for your password."
echo "           Ollama MUST be installed manually before you proceed."
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

# --- 1. Prerequisites ---
echo "--- Checking Prerequisites ---"

# Use doas for privilege escalation
if ! command_exists doas; then
    echo "ERROR: 'doas' command not found. This script requires 'doas' to install packages."
    echo "Please configure doas (similar to sudo) or run the required commands manually."
    exit 1
fi

# Python 3, Git, tmux
# Note: Adjust python version if needed. 3.11 is a common version in packages.
PACKAGES="python%3.11 git tmux"
echo "Checking for packages: $PACKAGES..."
for pkg in $PACKAGES; do
    if ! pkg_info -q "$pkg"; then
        echo "Package '$pkg' not found. Attempting to install..."
        doas pkg_add -I "$pkg"
        if ! pkg_info -q "$pkg"; then
            echo "ERROR: Failed to install '$pkg'. Please install it manually and re-run."
            exit 1
        fi
    else
        echo "Package '$pkg' is already installed."
    fi
done
echo "Prerequisites checked/installed."
echo ""

# --- 2. Ollama on OpenBSD - Instructions ---
echo "--- Ollama on OpenBSD (Manual Installation Required) ---"
echo "This script CANNOT install Ollama automatically on OpenBSD."
echo "You must build it from source. This is a complex process."
echo ""
echo "High-level steps are:"
echo "1. Install the Go compiler toolchain ('doas pkg_add go')."
echo "2. Install other build dependencies like 'cmake'."
echo "3. Clone the Ollama git repository from GitHub."
echo "4. Follow the instructions in the Ollama repository to build the 'ollama' binary."
echo "5. Place the final 'ollama' binary in a directory in your PATH (e.g., /usr/local/bin/)."
echo "6. Run 'ollama serve' in a separate terminal session."
echo ""
read -p "Have you already built and started the Ollama server in another terminal? (y/N) " ollama_host_ready
if [[ ! "$ollama_host_ready" =~ ^[Yy]$ ]]; then
    echo "Setup cannot proceed without a running Ollama server. Exiting."
    exit 1
fi

echo "Verifying connection to Ollama server..."
if ! curl -s http://localhost:11434/ >/dev/null 2>&1; then
    echo "ERROR: Could not connect to Ollama server at http://localhost:11434/"
    echo "Please ensure 'ollama serve' is running correctly in another terminal."
    exit 1
fi
echo "Successfully connected to Ollama server."
echo ""


# --- 3. Install Required Ollama Models ---
echo "--- Installing Ollama Models ---"
required_models=(
    "vitali87/shell-commands-qwen2-1.5b-q8_0-extended"
    "herawen/lisa"
    "nomic-embed-text"
    "qwen3:0.6b"
)
for model in "${required_models[@]}"; do
    echo "Pulling Ollama model: $model ..."
    ollama pull "$model"
    if ollama list | grep -q "${model%%:*}"; then
        echo "$model pulled successfully or already exists."
    else
        echo "WARNING: Failed to pull $model or could not verify. Please check manually."
    fi
done
echo ""

# --- 4. Setting up micro_X Python Environment ---
echo "--- Setting up Python Environment for micro_X ---"
VENV_DIR="$PROJECT_ROOT/.venv"
if [ -d "$VENV_DIR" ]; then
    echo "Python virtual environment '$VENV_DIR' already exists."
else
    echo "Creating Python virtual environment in '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then echo "ERROR: Failed to create virtual environment."; exit 1; fi
    echo "Virtual environment created."
fi

REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"

echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install -r "$REQUIREMENTS_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install Python dependencies."
    exit 1
fi
echo "Python dependencies installed."
echo ""

# --- 5. Make Scripts Executable ---
echo "--- Making Scripts Executable ---"
chmod +x "$PROJECT_ROOT/main.py"
if [ -f "$PROJECT_ROOT/micro_X.sh" ]; then
    chmod +x "$PROJECT_ROOT/micro_X.sh"
fi
echo "main.py and micro_X.sh are now executable."
echo ""

# --- 6. Setup Complete ---
echo "--- OpenBSD Setup for micro_X Complete! ---"
echo ""
echo "To run micro_X:"
echo "1. Ensure 'ollama serve' is running in a separate terminal."
echo "2. Navigate to the project directory: cd \"$PROJECT_ROOT\""
echo "3. Run the launch script: ./micro_X.sh"
echo ""
echo "------------------------------------------"

exit 0
