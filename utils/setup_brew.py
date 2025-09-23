#!/usr/bin/env python

import os
import sys
import subprocess
import logging
import argparse
import shutil
import platform

# --- Path Setup ---
try:
    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(script_path))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from utils.alias import handle_add_alias
except ImportError as e:
    print(f"❌ Error: Could not import necessary modules. Ensure this script is run from within the micro_X project structure.", file=sys.stderr)
    print(f"   Details: {e}", file=sys.stderr)
    sys.exit(1)

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def command_exists(command):
    """Checks if a command exists on the system."""
    return shutil.which(command) is not None

def is_wsl():
    """Checks if the environment is Windows Subsystem for Linux (WSL)."""
    if 'WSL_DISTRO_NAME' in os.environ:
        return True
    try:
        with open('/proc/version', 'r') as f:
            if 'microsoft' in f.read().lower():
                return True
    except FileNotFoundError:
        pass
    return False

def get_brew_executable_path():
    """
    Determines the path to the Homebrew executable by checking standard locations first,
    then falling back to shutil.which.
    """
    # Define standard installation paths
    standard_paths = []
    if sys.platform == "darwin": # macOS
        # Apple Silicon
        if platform.machine() == "arm64":
            standard_paths.append("/opt/homebrew/bin/brew")
        # Intel
        standard_paths.append("/usr/local/bin/brew")
    elif sys.platform.startswith("linux"): # Linux / WSL
        standard_paths.append("/home/linuxbrew/.linuxbrew/bin/brew")

    # Check standard paths first
    for path in standard_paths:
        if os.path.exists(path):
            logger.info(f"Found brew executable at standard path: {path}")
            return path

    # Fallback to checking the system PATH
    logger.info("Brew not found in standard locations, checking system PATH with shutil.which.")
    return shutil.which('brew')


def install_linux_prerequisites():
    """Installs prerequisites for Homebrew on Debian-based Linux."""
    environment_name = "WSL" if is_wsl() else "Linux"
    print(f"ℹ️ Homebrew on {environment_name} requires some prerequisite packages.")
    print("   This will attempt to install: build-essential, procps, curl, file, git")
    
    try:
        response = input(f"Do you want to proceed with installing these packages using 'sudo apt-get'? (y/N): ").lower()
        if response != 'y':
            print("🚫 Installation of prerequisites cancelled by user.")
            return False
        
        print("Updating package list with 'sudo apt-get update'...")
        subprocess.run(['sudo', 'apt-get', 'update'], check=True)
        
        print("Installing prerequisites...")
        subprocess.run(
            ['sudo', 'apt-get', 'install', '-y', 'build-essential', 'procps', 'curl', 'file', 'git'],
            check=True
        )
        print("✅ Prerequisites installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing prerequisites: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ An unexpected error occurred during prerequisite installation: {e}", file=sys.stderr)
        return False

def install_homebrew():
    """Installs Homebrew on macOS or Linux (including WSL)."""
    if command_exists('brew'):
        print("✅ Homebrew is already installed.")
        return True

    if sys.platform.startswith("linux"):
        if not install_linux_prerequisites():
            return False

    print("🍺 Homebrew not found. Attempting to install...")
    print("   Please follow any on-screen prompts from the Homebrew installer.")
    try:
        process = subprocess.run(
            '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
            shell=True,
            check=True
        )
        if process.returncode == 0:
            print("✅ Homebrew installed successfully.")
            return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing Homebrew: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ An unexpected error occurred during Homebrew installation: {e}", file=sys.stderr)
        return False

def setup_brew_path():
    """
    Detects the user's shell and adds the Homebrew path to the correct
    shell configuration file if it's not already present.
    """
    print("\n🔧 Checking shell environment for Homebrew path...")
    
    brew_executable_path = get_brew_executable_path()
    if not brew_executable_path:
        print("❌ Error: 'brew' command not found after installation. Cannot configure shell path.", file=sys.stderr)
        print("   Please follow the 'Next steps' from the Homebrew installer manually.", file=sys.stderr)
        return

    shell_path = os.environ.get("SHELL", "")
    shell_name = os.path.basename(shell_path)
    
    if shell_name in ["bash", "zsh"]:
        config_file = os.path.expanduser(f"~/.{shell_name}rc")
        if shell_name == "bash" and not os.path.exists(config_file):
            config_file = os.path.expanduser("~/.bash_profile")
            if not os.path.exists(config_file):
                 config_file = os.path.expanduser("~/.profile")
    else:
        config_file = os.path.expanduser("~/.profile")

    print(f"   Detected Shell: {shell_name}")
    print(f"   Configuration file to check/modify: {config_file}")

    brew_eval_command = f'eval "$({brew_executable_path} shellenv)"'
    
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                if any(brew_eval_command in line for line in f):
                    print("✅ Homebrew path is already configured in your shell profile.")
                    return
    except Exception as e:
        print(f"⚠️ Warning: Could not read {config_file} to check for existing config: {e}", file=sys.stderr)

    print(f"\nHomebrew path is not configured in {config_file}.")
    response = input(f"Do you want to automatically add the setup command to this file? (y/N): ").lower()
    
    if response == 'y':
        try:
            with open(config_file, 'a') as f:
                f.write('\n# Homebrew Setup for micro_X\n')
                f.write(f'{brew_eval_command}\n')
            print(f"✅ Successfully added Homebrew setup to {config_file}.")
            print("\nIMPORTANT: To apply the changes, please run the following command or restart your terminal:")
            print(f"  source {config_file}")
        except Exception as e:
            print(f"❌ Error: Could not write to {config_file}: {e}", file=sys.stderr)
            print("   Please add the following line to your shell configuration file manually:")
            print(f"   {brew_eval_command}")
    else:
        print("🚫 Shell configuration not modified.")
        print("   To use Homebrew, you must add the following line to your shell configuration file manually:")
        print(f"   {brew_eval_command}")

def main():
    """Main function to install Homebrew and create an alias."""
    parser = argparse.ArgumentParser(
        description="Install Homebrew on macOS, Debian-based Linux, or WSL and create an alias for it in micro_X.",
        epilog="This utility helps set up the Homebrew package manager and configures your shell environment."
    )
    parser.add_argument('--install', action='store_true', help='Run the Homebrew installation process.')

    args = parser.parse_args()

    if not args.install:
        parser.print_help()
        sys.exit(0)


    if args.install:
        if not (sys.platform == "darwin" or sys.platform.startswith("linux")):
            print("⚠️ This script is intended for macOS or Linux (including WSL) and may not work on other operating systems.", file=sys.stderr)
            sys.exit(1)

        if install_homebrew():
            setup_brew_path()

if __name__ == "__main__":
    main()
