#!/bin/bash

# Script to set up the micro_X environment on Linux Mint
# MODIFIED to be called from a root setup.sh and accept PROJECT_ROOT
# MODIFIED to create branch-specific .desktop files
# MODIFIED to update tmux session naming in instructions to match micro_X.sh

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

# Git (needed for branch detection for .desktop file and session name)
echo "Checking for git..."
if ! command_exists git; then
    echo "git not found. Attempting to install..."
    sudo apt update
    sudo apt install -y git
    if ! command_exists git; then
        echo "ERROR: Failed to install git. Please install it manually. Branch-specific features might not work as expected."
    else
        echo "git installed."
    fi
else
    echo "git is already installed."
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
        if ollama list | grep -q "${model%%:*}"; then
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

if [ ! -f "$PROJECT_ROOT/main.py" ]; then
    echo "ERROR: main.py not found in the project root ($PROJECT_ROOT)."
    exit 1
fi

VENV_DIR="$PROJECT_ROOT/.venv"
if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment '$VENV_DIR' already exists. Skipping creation."
else
    echo "Creating Python virtual environment in '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then echo "ERROR: Failed to create virtual environment."; exit 1; fi
    echo "Virtual environment created."
fi

REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
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

echo "Installing Python dependencies from $REQUIREMENTS_FILE into $VENV_DIR..."
"$VENV_DIR/bin/pip" install -r "$REQUIREMENTS_FILE"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install Python dependencies."
    echo "Try: source $VENV_DIR/bin/activate && pip install -r $REQUIREMENTS_FILE"
    exit 1
fi
echo "Python dependencies installed."
echo ""

# --- 4. Make Scripts Executable & Handle Desktop File ---
echo "--- Finalizing Scripts & Desktop Entry ---"
if [ -f "$PROJECT_ROOT/main.py" ]; then
    chmod +x "$PROJECT_ROOT/main.py"
    echo "main.py is now executable."
else
    echo "WARNING: main.py not found."
fi

MICRO_X_LAUNCHER_SH="$PROJECT_ROOT/micro_X.sh"
if [ -f "$MICRO_X_LAUNCHER_SH" ]; then
    chmod +x "$MICRO_X_LAUNCHER_SH"
    echo "micro_X.sh is now executable."
else
    echo "INFO: micro_X.sh (launch script) not found."
fi

DESKTOP_FILE_TEMPLATE_SOURCE="$PROJECT_ROOT/micro_X.desktop"
FINAL_DISPLAY_NAME_FOR_INSTRUCTIONS="micro_X" # Default for instructions

if [ -f "$DESKTOP_FILE_TEMPLATE_SOURCE" ]; then
    echo "Found desktop entry template: $DESKTOP_FILE_TEMPLATE_SOURCE."
    read -p "Do you want to install a desktop entry to your local applications menu? (y/N) " install_desktop_choice
    if [[ "$install_desktop_choice" =~ ^[Yy]$ ]]; then
        LOCAL_APPS_DIR="$HOME/.local/share/applications"
        mkdir -p "$LOCAL_APPS_DIR"

        CURRENT_BRANCH_NAME_SANITIZED="unknown"
        if command_exists git && [ -d "$PROJECT_ROOT/.git" ]; then
            BRANCH_OUTPUT=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)
            if [ $? -eq 0 ] && [ -n "$BRANCH_OUTPUT" ] && [ "$BRANCH_OUTPUT" != "HEAD" ]; then
                TEMP_SANITIZED_BRANCH_NAME=$(echo "$BRANCH_OUTPUT" | sed 's/\//_/g' | sed 's/[^a-zA-Z0-9_-]//g')
                if [ -n "$TEMP_SANITIZED_BRANCH_NAME" ]; then CURRENT_BRANCH_NAME_SANITIZED="$TEMP_SANITIZED_BRANCH_NAME"; fi
            elif [ "$BRANCH_OUTPUT" == "HEAD" ]; then
                # For detached HEAD, try to get a short commit hash for uniqueness
                COMMIT_HASH_SHORT=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null)
                if [ $? -eq 0 ] && [ -n "$COMMIT_HASH_SHORT" ]; then
                    CURRENT_BRANCH_NAME_SANITIZED="detached_${COMMIT_HASH_SHORT}"
                else
                    CURRENT_BRANCH_NAME_SANITIZED="detached"
                fi
            fi
        fi

        DESKTOP_FILENAME_BASE="micro_x"
        APP_NAME_BASE="micro_X"
        FINAL_DESKTOP_FILENAME="${DESKTOP_FILENAME_BASE}.desktop"
        FINAL_DISPLAY_NAME_FOR_INSTRUCTIONS="$APP_NAME_BASE" 
        FINAL_COMMENT_FOR_DESKTOP="Launch micro_X AI Shell"

        if [ "$CURRENT_BRANCH_NAME_SANITIZED" != "unknown" ]; then
            FINAL_DESKTOP_FILENAME="${DESKTOP_FILENAME_BASE}_${CURRENT_BRANCH_NAME_SANITIZED}.desktop"
            FINAL_DISPLAY_NAME_FOR_DESKTOP="${APP_NAME_BASE} (${CURRENT_BRANCH_NAME_SANITIZED})" 
            FINAL_DISPLAY_NAME_FOR_INSTRUCTIONS="$FINAL_DISPLAY_NAME_FOR_DESKTOP" 
            FINAL_COMMENT_FOR_DESKTOP="Launch micro_X AI Shell (${CURRENT_BRANCH_NAME_SANITIZED} instance)"
        else
            FINAL_DISPLAY_NAME_FOR_DESKTOP="$APP_NAME_BASE" 
        fi
        
        FINAL_DESKTOP_FILE_PATH="$LOCAL_APPS_DIR/$FINAL_DESKTOP_FILENAME"
        TEMP_DESKTOP_FILE=$(mktemp)
        cp "$DESKTOP_FILE_TEMPLATE_SOURCE" "$TEMP_DESKTOP_FILE"

        ESCAPED_LAUNCHER_PATH=$(echo "$MICRO_X_LAUNCHER_SH" | sed 's/\//\\\//g')
        sed -i "s|^Exec=.*|Exec=\"$ESCAPED_LAUNCHER_PATH\"|" "$TEMP_DESKTOP_FILE"
        sed -i "s|^Name=.*|Name=$FINAL_DISPLAY_NAME_FOR_DESKTOP|" "$TEMP_DESKTOP_FILE"
        sed -i "s|^Comment=.*|Comment=$FINAL_COMMENT_FOR_DESKTOP|" "$TEMP_DESKTOP_FILE"
        
        # Icon path handling (optional, if you have a project icon)
        # if grep -q "^Icon=" "$TEMP_DESKTOP_FILE" && ! grep -q "^Icon=/" "$TEMP_DESKTOP_FILE" && ! grep -q "^Icon=~" "$TEMP_DESKTOP_FILE"; then
        #    ICON_NAME=$(grep "^Icon=" "$TEMP_DESKTOP_FILE" | cut -d'=' -f2)
        #    ABSOLUTE_ICON_PATH="$PROJECT_ROOT/$ICON_NAME" 
        #    if [ -f "$ABSOLUTE_ICON_PATH" ]; then
        #        ESCAPED_PROJECT_ROOT_ICON_PATH=$(echo "$ABSOLUTE_ICON_PATH" | sed 's/\//\\\//g')
        #        sed -i "s|^Icon=.*|Icon=$ESCAPED_PROJECT_ROOT_ICON_PATH|" "$TEMP_DESKTOP_FILE"
        #    fi
        # fi

        echo "Copying modified desktop entry to $FINAL_DESKTOP_FILE_PATH..."
        cp "$TEMP_DESKTOP_FILE" "$FINAL_DESKTOP_FILE_PATH"
        rm "$TEMP_DESKTOP_FILE"

        if command_exists update-desktop-database; then
            echo "Updating desktop database..."
            update-desktop-database "$LOCAL_APPS_DIR"
        fi
        echo "Desktop entry '$FINAL_DISPLAY_NAME_FOR_DESKTOP' installed."
    else
        echo "Skipping installation of desktop entry."
    fi
else
    echo "INFO: $DESKTOP_FILE_TEMPLATE_SOURCE template not found. No desktop entry will be installed."
fi
echo ""

# --- 5. Setup Complete ---
echo "--- Setup Complete! ---"
echo ""
echo "To run micro_X:"
if [ -f "$DESKTOP_FILE_TEMPLATE_SOURCE" ] && [[ "$install_desktop_choice" =~ ^[Yy]$ ]]; then
    echo "1. Look for '$FINAL_DISPLAY_NAME_FOR_INSTRUCTIONS' in your desktop application menu."
    echo "   (It might take a few moments or a logout/login for it to appear)."
fi
echo "2. Alternatively, from the terminal:"
echo "   If you have micro_X.sh in the project root ($PROJECT_ROOT):"
echo "     cd \"$PROJECT_ROOT\" && ./micro_X.sh"
echo "     (This will launch micro_X in a tmux session. The session name will be based on your current Git branch,"
echo "      e.g., 'micro_x_main', 'micro_x_dev', or 'micro_x_detached_<hash>' if in detached HEAD state."
echo "      If not in a Git repository, it will use a default name like 'micro_x_app')."
echo ""
echo "   If running main.py directly (micro_X.sh usually handles this):"
echo "   a. Navigate to the project directory: cd \"$PROJECT_ROOT\""
echo "   b. Activate the virtual environment: source $VENV_DIR/bin/activate"
echo "   c. Run the main Python script: ./main.py (or python3 main.py)"
echo "      (Note: Running main.py directly will not use the branch-specific tmux session naming from micro_X.sh)."
echo ""
echo "Make sure the Ollama application is running and the required models are available."
echo "To attach to a running micro_X tmux session manually (e.g., if disconnected):"
echo "  Use 'tmux ls' to list all running tmux sessions and identify the correct session name."
echo "  Then, use: tmux attach-session -t <session_name>"
echo "  For example: tmux attach-session -t micro_x_dev"
echo "------------------------------------------"

exit 0
