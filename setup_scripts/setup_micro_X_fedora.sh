#!/bin/bash

# Script to set up the micro_X environment on Fedora

echo "--- micro_X Setup Script for Fedora (OS-Specific) ---"
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
echo "--- Checking Prerequisites (using dnf) ---"

# Python 3, PIP, Git, tmux
PACKAGES="python3 python3-pip git tmux"
echo "Checking for packages: $PACKAGES..."
# Check which packages are not installed
PACKAGES_TO_INSTALL=""
for pkg in $PACKAGES; do
    if ! rpm -q "$pkg" >/dev/null 2>&1; then
        PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL $pkg"
    else
        echo "Package '$pkg' is already installed."
    fi
done

if [ -n "$PACKAGES_TO_INSTALL" ]; then
    echo "The following packages are missing:$PACKAGES_TO_INSTALL"
    echo "Attempting to install with dnf (may require sudo)..."
    sudo dnf install -y$PACKAGES_TO_INSTALL
    # Verify again
    for pkg in $PACKAGES_TO_INSTALL; do
        if ! rpm -q "$pkg" >/dev/null 2>&1; then
            echo "ERROR: Failed to install '$pkg'. Please install it manually and re-run."
            exit 1
        fi
    done
    echo "All required packages installed."
else
    echo "All prerequisites are already installed."
fi
echo ""

# --- 2. Ollama Setup ---
echo "--- Ollama Setup ---"
if ! command_exists ollama; then
    echo "Ollama not found. Attempting to install using the official script..."
    curl -fsSL https://ollama.com/install.sh | sh
    if ! command_exists ollama; then
        echo "ERROR: Ollama installation failed. Please try installing it manually from https://ollama.com/ and re-run this script."
        exit 1
    fi
    echo "Ollama installed successfully."
else
    echo "Ollama is already installed."
fi

echo "Ensuring Ollama service is running..."
if ! systemctl is-active --quiet ollama; then
    echo "Ollama service is not active. Attempting to start (may require sudo)..."
    sudo systemctl start ollama
    sleep 5 # Give it a moment to start
    if ! systemctl is-active --quiet ollama; then
        echo "WARNING: Could not start Ollama service. Please ensure it's running manually before using micro_X."
    else
        echo "Ollama service started."
    fi
else
    echo "Ollama service appears to be running."
fi
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
echo "--- Fedora Setup for micro_X Complete! ---"
echo ""
echo "To run micro_X:"
echo "1. Ensure the Ollama service is running ('systemctl status ollama')."
echo "2. Navigate to the project directory: cd \"$PROJECT_ROOT\""
echo "3. Run the launch script: ./micro_X.sh"
echo ""
echo "------------------------------------------"

exit 0
