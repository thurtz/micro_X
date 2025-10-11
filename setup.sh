#!/bin/bash

# Unified Setup Script for micro_X
# This script detects the OS or allows manual selection, then calls the appropriate
# OS-specific setup script from the 'setup_scripts' directory.

# --- Helper Functions ---
echo_header() {
    echo ""
    echo "------------------------------------------"
    echo "--- $1 ---"
    echo "------------------------------------------"
    echo ""
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- Determine Project Root ---
# This script (setup.sh) is expected to be in the project root.
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SETUP_SCRIPTS_DIR="$PROJECT_ROOT/setup_scripts"

echo_header "micro_X Unified Setup"
echo "Project Root determined as: $PROJECT_ROOT"
echo "Setup scripts directory: $SETUP_SCRIPTS_DIR"

# --- OS Detection ---
OS_DETECTED=""
OS_NAME=""

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS_DETECTED="linux" # Default for linux-gnu
    # Check for WSL first, as it's a specific environment on top of a Linux distro
    if grep -qi microsoft /proc/version || [[ -n "$WSL_DISTRO_NAME" ]]; then
        OS_DETECTED="wsl"
        OS_NAME="WSL ($WSL_DISTRO_NAME)"
    # Then check for Termux, another specific environment
    elif [[ -n "$TERMUX_VERSION" ]]; then
        OS_DETECTED="termux"
        OS_NAME="Termux"
    # Fallback to general Linux distribution detection
    elif [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        source /etc/os-release
        OS_NAME=$NAME
        if [[ "$ID" == "linuxmint"* || "$ID_LIKE" == *"debian"* || "$ID_LIKE" == *"ubuntu"* || "$ID" == "ubuntu"* || "$ID" == "debian"* ]]; then
            OS_DETECTED="linux-mint-like" # Specific for Mint/Debian/Ubuntu
        fi
    elif command_exists lsb_release; then
        OS_NAME=$(lsb_release -is)
        if [[ "$OS_NAME" == "LinuxMint"* || "$OS_NAME" == "Ubuntu"* || "$OS_NAME" == "Debian"* ]]; then
             OS_DETECTED="linux-mint-like"
        fi
    fi

elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS_DETECTED="macos"
    OS_NAME="macOS"
fi

# --- OS Selection Menu ---
SELECTED_SCRIPT=""

if [[ -n "$OS_DETECTED" ]]; then
    echo "Detected OS: $OS_NAME ($OS_DETECTED)"
    case "$OS_DETECTED" in
        "linux-mint-like")
            read -p "Detected a Mint/Debian/Ubuntu-like Linux. Use Mint setup? (Y/n/menu): " choice
            if [[ "$choice" =~ ^[Yy]$ ]] || [[ -z "$choice" ]]; then
                SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_mint.sh"
            elif [[ "$choice" =~ ^[Mm] ]]; then
                OS_DETECTED="" # Force menu
            fi
            ;;
        "macos")
            read -p "Detected macOS. Use macOS setup? (Y/n/menu): " choice
            if [[ "$choice" =~ ^[Yy]$ ]] || [[ -z "$choice" ]]; then
                SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_mac.sh"
            elif [[ "$choice" =~ ^[Mm] ]]; then
                OS_DETECTED="" # Force menu
            fi
            ;;
        "termux")
            read -p "Detected Termux. Use Termux setup? (Y/n/menu): " choice
            if [[ "$choice" =~ ^[Yy]$ ]] || [[ -z "$choice" ]]; then
                SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_termux.sh"
            elif [[ "$choice" =~ ^[Mm] ]]; then
                OS_DETECTED="" # Force menu
            fi
            ;;
        "wsl")
            read -p "Detected WSL. Use WSL setup? (Y/n/menu): " choice
            if [[ "$choice" =~ ^[Yy]$ ]] || [[ -z "$choice" ]]; then
                SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_wsl.sh"
            elif [[ "$choice" =~ ^[Mm] ]]; then
                OS_DETECTED="" # Force menu
            fi
            ;;
        *)
            echo "Could not reliably auto-detect a specific setup script. Please choose manually."
            OS_DETECTED="" # Force menu
            ;;
    esac
fi

if [[ -z "$SELECTED_SCRIPT" ]] && [[ -z "$OS_DETECTED" ]]; then # If auto-detection failed or user chose menu
    echo_header "Manual OS Setup Selection"
    echo "Please choose the setup script for your Operating System:"
    echo "1. Linux Mint / Debian / Ubuntu"
    echo "2. macOS"
    echo "3. Termux (Android)"
    echo "4. WSL (Windows Subsystem for Linux)"
    echo "5. Exit"
    read -p "Enter your choice (1-5): " menu_choice

    case "$menu_choice" in
        1) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_mint.sh" ;;
        2) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_mac.sh" ;;
        3) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_termux.sh" ;;
        4) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_wsl.sh" ;;
        5) echo "Exiting setup."; exit 0 ;;
        *) echo "Invalid choice. Exiting."; exit 1 ;;
    esac
fi

# --- Execute Selected Script ---
if [[ -n "$SELECTED_SCRIPT" ]] && [[ -f "$SELECTED_SCRIPT" ]]; then
    echo_header "Launching Selected Setup Script"
    echo "Executing: $SELECTED_SCRIPT"
    echo "Passing Project Root: $PROJECT_ROOT"
    echo ""
    # Make the selected script executable just in case and then run it, passing the PROJECT_ROOT
    chmod +x "$SELECTED_SCRIPT"
    # Pass PROJECT_ROOT as the first argument to the OS-specific script
    bash "$SELECTED_SCRIPT" "$PROJECT_ROOT"
    exit_code=$?
    if [ $exit_code -eq 0 ]; then
        echo_header "Setup script completed successfully."
    else
        echo_header "Setup script failed with exit code $exit_code."
    fi
    exit $exit_code
elif [[ -n "$SELECTED_SCRIPT" ]]; then
    echo "ERROR: Selected setup script '$SELECTED_SCRIPT' not found or is not a file."
    exit 1
else
    echo "ERROR: No setup script was selected or determined. Exiting."
    exit 1
fi