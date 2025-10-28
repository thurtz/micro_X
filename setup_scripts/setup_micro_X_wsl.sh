#!/bin/bash

# Script to set up the micro_X environment within WSL (Windows Subsystem for Linux)
# This script assumes Ollama is installed and running on the WINDOWS HOST.
# MODIFIED to be called from a root setup.sh and accept PROJECT_ROOT

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

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- 1. Prerequisites for WSL Environment ---
echo "--- Checking WSL Prerequisites ---"

# Update package list
echo "Updating package list (sudo apt update)..."
sudo apt update
echo ""

# Python 3, PIP, venv
echo "Checking for Python 3, PIP, and venv..."
PACKAGES_TO_INSTALL=""
if ! command_exists python3; then PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL python3"; fi
if ! command_exists pip3; then PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL python3-pip"; fi
# Check for python3-venv specifically, as just python3-pip might not install it.
if ! dpkg -s python3-venv >/dev/null 2>&1 && ! python3 -m venv --help >/dev/null 2>&1; then
    PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL python3-venv"
fi


if [ -n "$PACKAGES_TO_INSTALL" ]; then
    echo "The following Python-related packages are missing or not fully installed: $PACKAGES_TO_INSTALL"
    echo "Attempting to install..."
    sudo apt install -y $PACKAGES_TO_INSTALL
    # Verify again
    if ! command_exists python3 || ! command_exists pip3 || (! dpkg -s python3-venv >/dev/null 2>&1 && ! python3 -m venv --help >/dev/null 2>&1); then
        echo "ERROR: Failed to install all required Python packages. Please install them manually and re-run."
        exit 1
    fi
    echo "Python packages installed."
else
    echo "Python 3, PIP3, and python3-venv (or equivalent) are already installed."
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

# --- 2. Ollama on Windows Host - Instructions ---
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
    # Optionally exit, or let user proceed with WSL-side setup
    # exit 1
fi
echo ""

# --- 3. Ollama Model Pulling - Instructions ---
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

# --- 4. Setting up micro_X Python Environment in WSL ---
echo "--- Setting up Python Environment for micro_X (in WSL) ---"

# Check if main.py exists in PROJECT_ROOT
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
    echo "Creating Python virtual environment in '$VENV_DIR'..."
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
numpy>=1.20.0
EOF
    echo "$REQUIREMENTS_FILE created."
else
    echo "$REQUIREMENTS_FILE already exists."
fi

# Install Python Dependencies into the virtual environment
echo "Installing Python dependencies from $REQUIREMENTS_FILE into $VENV_DIR..."
"$VENV_DIR/bin/pip3" install -r "$REQUIREMENTS_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install Python dependencies."
    echo "Try activating the virtual environment manually ('source $VENV_DIR/bin/activate') and then run 'pip3 install -r $REQUIREMENTS_FILE'."
    exit 1
fi
echo "Python dependencies installed."
echo ""

# --- 5. Make Scripts Executable ---
echo "--- Making Scripts Executable (in WSL) ---"
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

# --- 6. OLLAMA_HOST Configuration Reminder ---
echo "--- IMPORTANT: OLLAMA_HOST Configuration ---"
echo "For micro_X in WSL to connect to Ollama on your Windows host, you MUST set the OLLAMA_HOST environment variable."
echo "Typically, for WSL2, Ollama on Windows is accessible via http://localhost:11434 from within WSL."
echo ""
echo "You can set this variable temporarily before running micro_X:"
echo "  export OLLAMA_HOST=http://localhost:11434"
echo "  cd \"$PROJECT_ROOT\" && ./micro_X.sh" # MODIFIED to show context
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

echo "The micro_X.sh script in '$PROJECT_ROOT' might also be a good place to set this variable if it's not set globally." # MODIFIED

echo "Verify connectivity from WSL to Ollama on Windows with: curl http://localhost:11434"
echo "(You may need to install curl: sudo apt install curl)"
echo "Also, ensure your Windows Firewall is not blocking connections to port 11434 from WSL."
echo ""


# --- 7. Setup Complete ---
echo "--- WSL Setup for micro_X Complete! ---"
echo ""
echo "To run micro_X:"
echo "1. Ensure Ollama is installed and RUNNING on your WINDOWS host."
echo "2. Ensure you have pulled the required Ollama models on your WINDOWS host."
echo "3. Open your WSL terminal."
echo "4. Navigate to the micro_X directory: cd \"$PROJECT_ROOT\"" # MODIFIED
echo "5. Set the OLLAMA_HOST environment variable if not already set permanently:"
echo "   export OLLAMA_HOST=http://localhost:11434"
echo "6. If you have micro_X.sh (recommended):"
echo "   ./micro_X.sh"
echo "   (The micro_X.sh script should activate the virtual environment)."
echo ""
echo "   If running main.py directly:"
echo "   source .venv/bin/activate"
echo "   ./main.py  # or python3 main.py"
echo ""
echo "------------------------------------------"

exit 0
