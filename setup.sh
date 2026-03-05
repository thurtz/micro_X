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
            # Check for Termux, another specific environment
            if [[ -n "$TERMUX_VERSION" ]]; then        OS_DETECTED="termux"
        OS_NAME="Termux"
    # Fallback to general Linux distribution detection
    elif [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        source /etc/os-release
        OS_NAME=$NAME
        if [[ "$ID" == "linuxmint"* || "$ID_LIKE" == *"debian"* || "$ID_LIKE" == *"ubuntu"* || "$ID" == "ubuntu"* || "$ID" == "debian"* ]]; then
            OS_DETECTED="linux-mint-like" # Specific for Mint/Debian/Ubuntu
        elif [[ "$ID" == "fedora" ]]; then
            OS_DETECTED="fedora"
        elif [[ "$ID" == "arch" || "$ID_LIKE" == *"arch"* ]]; then
            OS_DETECTED="arch"
        elif [[ "$ID" == "rhel" || "$ID_LIKE" == *"rhel"* || "$ID_LIKE" == *"fedora"* ]]; then
            OS_DETECTED="rhel"
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
elif [[ "$OSTYPE" == "openbsd"* ]]; then
    OS_DETECTED="openbsd"
    OS_NAME="OpenBSD"
elif [[ "$OSTYPE" == "freebsd"* ]]; then
    OS_DETECTED="freebsd"
    OS_NAME="FreeBSD"
elif [[ "$OSTYPE" == "netbsd"* ]]; then
    OS_DETECTED="netbsd"
    OS_NAME="NetBSD"
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
                    "openbsd")            read -p "Detected OpenBSD. Use OpenBSD setup? (Y/n/menu): " choice
            if [[ "$choice" =~ ^[Yy]$ ]] || [[ -z "$choice" ]]; then
                SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_openbsd.sh"
            elif [[ "$choice" =~ ^[Mm] ]]; then
                OS_DETECTED="" # Force menu
            fi
            ;;
        "fedora")
            read -p "Detected Fedora. Use Fedora setup? (Y/n/menu): " choice
            if [[ "$choice" =~ ^[Yy]$ ]] || [[ -z "$choice" ]]; then
                SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_fedora.sh"
            elif [[ "$choice" =~ ^[Mm] ]]; then
                OS_DETECTED="" # Force menu
            fi
            ;;
        "arch")
            read -p "Detected Arch Linux. Use Arch setup? (Y/n/menu): " choice
            if [[ "$choice" =~ ^[Yy]$ ]] || [[ -z "$choice" ]]; then
                SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_arch.sh"
            elif [[ "$choice" =~ ^[Mm] ]]; then
                OS_DETECTED="" # Force menu
            fi
            ;;
        "freebsd")
            read -p "Detected FreeBSD. Use FreeBSD setup? (Y/n/menu): " choice
            if [[ "$choice" =~ ^[Yy]$ ]] || [[ -z "$choice" ]]; then
                SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_freebsd.sh"
            elif [[ "$choice" =~ ^[Mm] ]]; then
                OS_DETECTED="" # Force menu
            fi
            ;;
        "netbsd")
            read -p "Detected NetBSD. Use NetBSD setup? (Y/n/menu): " choice
            if [[ "$choice" =~ ^[Yy]$ ]] || [[ -z "$choice" ]]; then
                SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_netbsd.sh"
            elif [[ "$choice" =~ ^[Mm] ]]; then
                OS_DETECTED="" # Force menu
            fi
            ;;
        "rhel")
            read -p "Detected RHEL-like Linux. Use RHEL setup? (Y/n/menu): " choice
            if [[ "$choice" =~ ^[Yy]$ ]] || [[ -z "$choice" ]]; then
                SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_rhel.sh"
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
    echo "4. OpenBSD"
    echo "5. Fedora"
    echo "6. Arch Linux"
    echo "7. FreeBSD"
    echo "8. NetBSD"
    echo "9. RHEL / CentOS"
    echo "10. Exit"
    read -p "Enter your choice (1-10): " menu_choice

    case "$menu_choice" in
        1) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_mint.sh" ;;
        2) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_mac.sh" ;;
        3) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_termux.sh" ;;
        4) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_openbsd.sh" ;;
        5) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_fedora.sh" ;;
        6) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_arch.sh" ;;
        7) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_freebsd.sh" ;;
        8) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_netbsd.sh" ;;
        9) SELECTED_SCRIPT="$SETUP_SCRIPTS_DIR/setup_micro_X_rhel.sh" ;;
        10) echo "Exiting setup."; exit 0 ;;
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