#!/bin/bash

# Script to set up the micro_X environment on Linux Mint
# MODIFIED to be called from a root setup.sh and accept PROJECT_ROOT

echo "--- micro_X Setup Script for Linux Mint (OS-Specific) ---"
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

# Python 3 and PIP
echo "Checking for Python 3 and PIP..."
if ! command_exists python3 || ! command_exists pip3; then
    echo "Python 3 and/or PIP3 not found. Attempting to install..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
    if ! command_exists python3 || ! command_exists pip3; then
        echo "ERROR: Failed to install Python 3 and/or PIP3. Please install them manually and re-run this script."
        exit 1
    fi
    echo "Python 3 and PIP3 installed."
else
    echo "Python 3 and PIP3 are already installed."
fi

# Python3-venv (specifically needed for python3 -m venv)
echo "Checking for python3-venv package..."
if ! dpkg -s python3-venv >/dev/null 2>&1; then
    echo "python3-venv package not found. Attempting to install..."
    sudo apt update
    sudo apt install -y python3-venv
    if ! dpkg -s python3-venv >/dev/null 2>&1; then
        echo "ERROR: Failed to install python3-venv. Please install it manually and re-run this script."
        exit 1
    fi
    echo "python3-venv installed."
else
    echo "python3-venv is already installed."
fi


# tmux
echo "Checking for tmux..."
if ! command_exists tmux; then
    echo "tmux not found. Attempting to install..."
    sudo apt update
    sudo apt install -y tmux
    if ! command_exists tmux; then
        echo "ERROR: Failed to install tmux. Please install it manually and re-run this script."
        exit 1
    fi
    echo "tmux installed."
else
    echo "tmux is already installed."
fi

# Ollama
echo "Checking for Ollama..."
if ! command_exists ollama; then
    echo "Ollama not found. This script cannot install Ollama automatically."
    echo "Please visit https://ollama.com/ to download and install it for your system."
    echo "After installing Ollama, ensure it is running, then re-run this script or manually pull the models."
else
    echo "Ollama is installed."
    echo "Ensuring Ollama service is running (this might take a moment or require sudo if not running)..."
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
fi
echo ""

# --- 2. Install Required Ollama Models ---
echo "--- Installing Ollama Models ---"
if command_exists ollama; then
    MODELS=(
        "llama3.2:3b"
        "vitali87/shell-commands-qwen2-1.5b"
        "herawen/lisa:latest"
    )
    for model in "${MODELS[@]}"; do
        echo "Pulling Ollama model: $model ..."
        ollama pull "$model"
        # Basic check if model is listed (name before ':')
        if ollama list | grep -q "${model%%:*}"; then # Check for the base model name
            echo "$model pulled successfully or already exists."
        else
            echo "WARNING: Failed to pull $model or could not verify. Please check manually."
        fi
    done
else
    echo "Skipping Ollama model installation because Ollama command was not found."
fi
echo ""

# --- 3. Setting up micro_X Python Environment ---
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
    echo "Virtual environment '$VENV_DIR' already exists. Skipping creation."
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
prompt_toolkit>=3.0.0
ollama>=0.1.0
EOF
    echo "$REQUIREMENTS_FILE created."
else
    echo "$REQUIREMENTS_FILE already exists."
fi

# Install Python Dependencies into the virtual environment
echo "Installing Python dependencies from $REQUIREMENTS_FILE into $VENV_DIR..."
"$VENV_DIR/bin/pip" install -r "$REQUIREMENTS_FILE" # Use pip from venv
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install Python dependencies."
    echo "Try activating the virtual environment manually ('source $VENV_DIR/bin/activate') and then run 'pip install -r $REQUIREMENTS_FILE'."
    exit 1
fi
echo "Python dependencies installed."
echo ""

# --- 4. Make Scripts Executable & Handle Desktop File ---
echo "--- Finalizing Scripts & Desktop Entry ---"
if [ -f "$PROJECT_ROOT/main.py" ]; then # MODIFIED
    chmod +x "$PROJECT_ROOT/main.py" # MODIFIED
    echo "main.py is now executable."
else
    echo "WARNING: main.py not found, cannot make executable."
fi

MICRO_X_LAUNCHER_SH="$PROJECT_ROOT/micro_X.sh" # MODIFIED
if [ -f "$MICRO_X_LAUNCHER_SH" ]; then
    chmod +x "$MICRO_X_LAUNCHER_SH"
    echo "micro_X.sh is now executable."
else
    echo "INFO: micro_X.sh (launch script) not found. If you have one, ensure it's executable."
fi

DESKTOP_FILE_SOURCE="$PROJECT_ROOT/micro_X.desktop" # MODIFIED
if [ -f "$DESKTOP_FILE_SOURCE" ]; then
    echo "Found $DESKTOP_FILE_SOURCE."

    read -p "Do you want to install the $DESKTOP_FILE_SOURCE to your local applications menu? (y/N) " install_desktop_choice
    if [[ "$install_desktop_choice" =~ ^[Yy]$ ]]; then
        LOCAL_APPS_DIR="$HOME/.local/share/applications"
        mkdir -p "$LOCAL_APPS_DIR"

        TEMP_DESKTOP_FILE=$(mktemp)
        cp "$DESKTOP_FILE_SOURCE" "$TEMP_DESKTOP_FILE"

        # Ensure Exec path in .desktop file points to micro_X.sh in PROJECT_ROOT
        ESCAPED_LAUNCHER_PATH=$(echo "$MICRO_X_LAUNCHER_SH" | sed 's/\//\\\//g') # Escape slashes for sed
        sed -i "s/^Exec=.*/Exec=\"$ESCAPED_LAUNCHER_PATH\"/" "$TEMP_DESKTOP_FILE"
        
        # Example for updating Icon path if it's relative and icon is in PROJECT_ROOT
        # Assuming Icon=some_icon.png and the icon is in $PROJECT_ROOT/assets/some_icon.png
        # This part needs to be adapted if you have an icon and know its relative path
        # For now, we assume Exec is the main thing to fix.
        # If Icon line exists and is relative (does not start with / or ~)
        # if grep -q "^Icon=[^/~]" "$TEMP_DESKTOP_FILE"; then
        #    ICON_NAME=$(grep "^Icon=" "$TEMP_DESKTOP_FILE" | cut -d'=' -f2)
        #    ESCAPED_PROJECT_ROOT_ICON_PATH=$(echo "$PROJECT_ROOT/$ICON_NAME" | sed 's/\//\\\//g')
        #    sed -i "s/^Icon=.*/Icon=$ESCAPED_PROJECT_ROOT_ICON_PATH/" "$TEMP_DESKTOP_FILE"
        #    echo "Updated Icon path in .desktop file to be absolute: $PROJECT_ROOT/$ICON_NAME"
        # fi


        echo "Copying modified $DESKTOP_FILE_SOURCE to $LOCAL_APPS_DIR/micro_X.desktop..."
        cp "$TEMP_DESKTOP_FILE" "$LOCAL_APPS_DIR/micro_X.desktop"
        rm "$TEMP_DESKTOP_FILE" 

        if command_exists update-desktop-database; then
            echo "Updating desktop database..."
            update-desktop-database "$LOCAL_APPS_DIR"
        fi
        echo "micro_X.desktop installed. You should find 'micro_X' in your application menu."
    else
        echo "Skipping installation of $DESKTOP_FILE_SOURCE to applications menu."
        echo "You can manually copy and modify it to $HOME/.local/share/applications/ or /usr/share/applications/ later if desired."
    fi
else
    echo "INFO: $DESKTOP_FILE_SOURCE not found. No desktop entry will be installed."
fi
echo ""

# --- 5. Setup Complete ---
echo "--- Setup Complete! ---"
echo ""
echo "To run micro_X:"
if [ -f "$DESKTOP_FILE_SOURCE" ] && [[ "$install_desktop_choice" =~ ^[Yy]$ ]]; then
    echo "1. Look for 'micro_X' in your desktop application menu."
    echo "   (It might take a few moments or a logout/login for it to appear)."
fi
echo "2. Alternatively, from the terminal:"
echo "   If you have micro_X.sh in the project root ($PROJECT_ROOT):" # MODIFIED
echo "     cd \"$PROJECT_ROOT\" && ./micro_X.sh" # MODIFIED
echo ""
echo "   If running main.py directly (micro_X.sh usually handles this):"
echo "   a. Navigate to the project directory: cd \"$PROJECT_ROOT\"" # MODIFIED
echo "   b. Activate the virtual environment: source $VENV_DIR/bin/activate"
echo "   c. Run the main Python script: ./main.py (or python3 main.py)"
echo ""
echo "Make sure the Ollama application is running and the required models are available."
echo "------------------------------------------"

exit 0
