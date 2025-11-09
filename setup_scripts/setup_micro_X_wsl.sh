#!/bin/bash

# Script to set up the micro_X environment within WSL (Windows Subsystem for Linux)
# This script assumes Ollama is installed and running on the WINDOWS HOST.
# MODIFIED to be called from a root setup.sh and accept PROJECT_ROOT
# UPDATED to use pyenv for Python version management.

echo "--- micro_X Setup Script for WSL (OS-Specific) ---"
echo ""
echo "IMPORTANT ASSUMPTIONS:"
echo "1. You are running this script INSIDE your WSL (e.g., Ubuntu) environment."
echo "2. Ollama is (or will be) installed and RUNNING on your WINDOWS HOST machine."
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

# --- Define Python Version and .python-version file ---
PYTHON_VERSION="3.13.5" # Default Python version for the project
PYTHON_VERSION_FILE="$PROJECT_ROOT/.python-version"

if [ ! -f "$PYTHON_VERSION_FILE" ]; then
    echo "Creating $PYTHON_VERSION_FILE with version $PYTHON_VERSION..."
    echo "$PYTHON_VERSION" > "$PYTHON_VERSION_FILE"
    echo ".python-version file created."
else
    PYTHON_VERSION=$(cat "$PYTHON_VERSION_FILE")
    echo "Using Python version from $PYTHON_VERSION_FILE: $PYTHON_VERSION"
fi
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if pyenv is installed
check_pyenv_installed() {
    if command_exists pyenv; then
        echo "pyenv is already installed."
        return 0
    else
        echo "pyenv is not installed."
        return 1
    fi
}

# Function to install pyenv from git
install_pyenv_from_git() {
    echo "Attempting to install pyenv from Git..."

    # Install build dependencies for Python versions
    echo "Installing pyenv build dependencies..."
    sudo apt update
    sudo apt install -y make build-essential libssl-dev zlib1g-dev \
        libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
        libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install pyenv build dependencies. Please install them manually and re-run."
        exit 1
    fi

    # Clone pyenv
    if [ ! -d "$HOME/.pyenv" ]; then
        git clone https://github.com/pyenv/pyenv.git "$HOME/.pyenv"
        if [ $? -ne 0 ]; then
            echo "ERROR: Failed to clone pyenv repository."
            exit 1
        fi
    else
        echo "$HOME/.pyenv already exists. Skipping cloning."
    fi

    # Add pyenv to shell environment (for bash)
    if ! grep -q 'export PYENV_ROOT' "$HOME/.bashrc"; then
        echo "Configuring pyenv in ~/.bashrc..."
        echo 'export PYENV_ROOT="$HOME/.pyenv"' >> "$HOME/.bashrc"
        echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> "$HOME/.bashrc"
        echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n  eval "$(pyenv init --path)"\nfi' >> "$HOME/.bashrc"
        echo "Please restart your terminal or run 'source ~/.bashrc' for pyenv to be fully active."
    else
        echo "pyenv configuration already present in ~/.bashrc."
    fi

    # Source bashrc to make pyenv available in the current script context
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init --path)"
    
    if command_exists pyenv; then
        echo "pyenv installed and configured successfully in current session."
        return 0
    else
        echo "ERROR: pyenv command not found after installation attempt. Please check your setup."
        exit 1
    fi
}

# --- 1. Prerequisites for WSL Environment ---
echo "--- Checking WSL Prerequisites ---"

# Update package list
echo "Updating package list (sudo apt update)..."
sudo apt update
echo ""

# Git (needed for pyenv)
echo "Checking for git..."
if ! command_exists git; then
    echo "git not found. Attempting to install..."
    sudo apt install -y git
    if ! command_exists git; then
        echo "ERROR: Failed to install git. Please install it manually."
        exit 1
    else
        echo "git installed."
    fi
else
    echo "git is already installed."
fi

# tmux
echo "Checking for tmux..."
if ! command_exists tmux; then
    echo "tmux not found. Attempting to install..."
    sudo apt install -y tmux
    if ! command_exists tmux; then
        echo "ERROR: Failed to install tmux. Please install it manually ('sudo apt install tmux') and re-run."
        exit 1
    fi
    echo "tmux installed."
else
    echo "tmux is already installed."
fi
echo ""

# --- 2. Python Version Management with pyenv ---
echo "--- Setting up Python with pyenv ---"

# Ensure pyenv is installed
if ! check_pyenv_installed; then
    install_pyenv_from_git
    # After installation, ensure pyenv is available in the current shell
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init --path)"
    if ! command_exists pyenv; then
        echo "ERROR: pyenv not available after installation. Please restart your terminal and re-run the setup script."
        exit 1
    fi
fi

# Install the required Python version using pyenv
echo "Installing Python version $PYTHON_VERSION using pyenv..."
if ! pyenv install --skip-existing "$PYTHON_VERSION"; then
    echo "ERROR: Failed to install Python $PYTHON_VERSION using pyenv. Please check pyenv logs."
    exit 1
fi
echo "Python $PYTHON_VERSION installed via pyenv."

# Set the local Python version for the project
echo "Setting local pyenv Python version to $PYTHON_VERSION..."
if ! pyenv local "$PYTHON_VERSION"; then
    echo "ERROR: Failed to set local pyenv Python version. Ensure pyenv is correctly initialized."
    exit 1
fi
echo "Local pyenv Python version set to $PYTHON_VERSION."
echo ""

# --- 3. Ollama on Windows Host - Instructions ---
echo "--- Ollama on Windows Host (Instructions) ---"
echo "This script will NOT install Ollama on your Windows host."
echo "Please ensure you have done the following on your WINDOWS machine:"
echo "1. Download and install Ollama for Windows from https://ollama.com/"
echo "2. Run the Ollama application on Windows. It should be running in the background."
echo "   (You might see an Ollama icon in your Windows system tray)."
echo ""
read -p "Have you installed and started Ollama on your WINDOWS host? (y/N) " ollama_host_ready
if [[ ! "$ollama_host_ready" =~ ^[Yy]$ ]]; then
    echo "Ollama on Windows host is not ready. Please set it up and then re-run this script or proceed manually."
fi
echo ""

# --- 4. Ollama Model Pulling - Instructions ---
echo "--- Ollama Model Pulling (Instructions for Windows Host) ---"
echo "The following Ollama models are required by micro_X:"
required_models=(
    "vitali87/shell-commands-qwen2-1.5b-q8_0-extended"
    "herawen/lisa"
    "nomic-embed-text"
    "qwen3:0.6b"
)
for model in "${required_models[@]}"; do
    echo "  ollama pull $model"
done
echo ""
read -p "Have you pulled these models on your WINDOWS host using the Windows Ollama CLI? (y/N) " models_pulled
if [[ ! "$models_pulled" =~ ^[Yy]$ ]]; then
    echo "Model pulling was skipped or not confirmed. micro_X requires these models to function correctly."
fi
echo ""

# --- 5. Setting up micro_X Python Environment in WSL ---
echo "--- Setting up Python Environment for micro_X (in WSL) ---"

if [ ! -f "$PROJECT_ROOT/main.py" ]; then
    echo "ERROR: main.py not found in the project root ($PROJECT_ROOT)."
    exit 1
fi

VENV_DIR="$PROJECT_ROOT/.venv"
if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment '$VENV_DIR' already exists. Skipping creation."
else
    echo "Creating Python virtual environment in '$VENV_DIR' using pyenv-managed Python..."
    # Use 'python' which should now be managed by pyenv due to 'pyenv local'
    python -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then echo "ERROR: Failed to create virtual environment."; exit 1; fi
    echo "Virtual environment created."
fi

REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "Creating $REQUIREMENTS_FILE..."
    cat <<EOF > "$REQUIREMENTS_FILE"
# Python dependencies for micro_X
prompt_toolkit>=3.0.0
ollama>=0.1.0
numpy>=1.20.0
EOF
    echo "$REQUIREMENTS_FILE created."
else
    echo "$REQUIREMENTS_FILE already exists."
fi

echo "Installing Python dependencies from $REQUIREMENTS_FILE into $VENV_DIR..."
"$VENV_DIR/bin/pip" install -r "$REQUIREMENTS_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install Python dependencies."
    echo "Try: source $VENV_DIR/bin/activate && pip install -r $REQUIREMENTS_FILE"
    exit 1
fi
echo "Python dependencies installed."
echo ""

# --- 6. Make Scripts Executable ---
echo "--- Making Scripts Executable (in WSL) ---"
if [ -f "$PROJECT_ROOT/main.py" ]; then
    chmod +x "$PROJECT_ROOT/main.py"
    echo "main.py is now executable."
fi

MICRO_X_LAUNCHER_SH="$PROJECT_ROOT/micro_X.sh"
if [ -f "$MICRO_X_LAUNCHER_SH" ]; then
    chmod +x "$MICRO_X_LAUNCHER_SH"
    echo "micro_X.sh is now executable."
else
    echo "INFO: micro_X.sh (launch script) not found. This script is recommended for running micro_X."
fi
echo ""

# --- 7. OLLAMA_HOST Configuration Reminder ---
echo "--- IMPORTANT: OLLAMA_HOST Configuration ---"
echo "For micro_X in WSL to connect to Ollama on your Windows host, you MUST set the OLLAMA_HOST environment variable."
echo "Typically, for WSL2, Ollama on Windows is accessible via http://localhost:11434 from within WSL."
echo ""
echo "You can set this variable temporarily before running micro_X:"
echo "  export OLLAMA_HOST=http://localhost:11434"
echo "  cd \"$PROJECT_ROOT\" && ./micro_X.sh"
echo ""
echo "For a permanent setting, add the export line to your WSL shell's configuration file"
echo "(e.g., ~/.bashrc if using bash, or ~/.zshrc if using zsh), then source it or open a new terminal:"
echo "  echo 'export OLLAMA_HOST=http://localhost:11434' >> ~/.bashrc"
echo "  source ~/.bashrc"
echo ""

echo "Attempting to verify connectivity from WSL to Ollama on Windows..."
if ! command_exists curl; then
    echo "curl command not found. Installing it to verify connection..."
    sudo apt install -y curl
fi

if curl --fail --silent --show-error http://localhost:11434/ >/dev/null 2>&1; then
    echo "✅ Successfully connected to Ollama on the Windows host."
else
    echo "❌ WARNING: Could not connect to Ollama on your Windows host at http://localhost:11434/"
    echo "   This is required for micro_X to function."
    echo "   TROUBLESHOOTING:"
    echo "   1. Is the Ollama application installed and RUNNING on your Windows machine?"
    echo "   2. Did you set the OLLAMA_HOST variable correctly? (run 'export OLLAMA_HOST=http://localhost:11434')"
    echo "   3. Is your Windows Firewall blocking connections from WSL? You may need to allow incoming connections on port 11434."
    echo "   You can proceed with the setup, but AI features will not work until this is resolved."
fi
echo ""

# --- 8. Setup Complete ---
echo "--- WSL Setup for micro_X Complete! ---"
echo ""
echo "To run micro_X:"
echo "1. Ensure Ollama is installed and RUNNING on your WINDOWS host."
echo "2. Ensure you have pulled the required Ollama models on your WINDOWS host."
echo "3. Open your WSL terminal."
echo "4. Navigate to the micro_X directory: cd \"$PROJECT_ROOT\""
echo "5. Set the OLLAMA_HOST environment variable if not already set permanently:"
echo "   export OLLAMA_HOST=http://localhost:11434"
echo "6. If you have micro_X.sh (recommended):"
echo "   ./micro_X.sh"
echo "   (This will launch micro_X in a tmux session and use the correct pyenv Python version)."
echo ""
echo "   If running main.py directly:"
echo "   a. Navigate to the project directory: cd \"$PROJECT_ROOT\""
echo "   b. Activate the virtual environment: source .venv/bin/activate"
echo "   c. Run the main Python script: ./main.py (or python3 main.py)"
echo ""
echo "------------------------------------------"

exit 0