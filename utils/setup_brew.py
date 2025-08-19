#!/usr/bin/env python

import os
import sys
import subprocess
import logging
import argparse

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
    """Checks if a command exists on the system by checking its path."""
    return any(os.access(os.path.join(path, command), os.X_OK) for path in os.environ["PATH"].split(os.pathsep))

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

    # Install prerequisites if on Linux/WSL
    if sys.platform.startswith("linux"):
        if not install_linux_prerequisites():
            return False

    print("🍺 Homebrew not found. Attempting to install...")
    print("   Please follow any on-screen prompts from the Homebrew installer.")
    try:
        # The official installer script works for macOS, Linux, and WSL
        # We run it without capturing output so the user can interact with it (e.g., enter password)
        process = subprocess.run(
            '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
            shell=True,
            check=True
        )
        if process.returncode == 0:
            print("✅ Homebrew installed successfully.")
            print("\nIMPORTANT: Please follow the 'Next steps' instructions printed by the")
            print("Homebrew installer to add Homebrew to your PATH.")
            if is_wsl():
                print("   For WSL, this typically involves adding a line to your ~/.profile or ~/.bashrc file.")
            return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing Homebrew: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ An unexpected error occurred during Homebrew installation: {e}", file=sys.stderr)
        return False

def main():
    """Main function to install Homebrew and create an alias."""
    parser = argparse.ArgumentParser(
        description="Install Homebrew on macOS, Debian-based Linux, or WSL and create an alias for it in micro_X.",
        epilog="This utility helps set up the Homebrew package manager."
    )
    parser.parse_args()

    if not (sys.platform == "darwin" or sys.platform.startswith("linux")):
        print("⚠️ This script is intended for macOS or Linux (including WSL) and may not work on other operating systems.", file=sys.stderr)
        sys.exit(1)

    if install_homebrew():
        # After successful installation, create the alias
        print("\n🔗 Creating alias '/brew'...")
        
        # We need to simulate the argparse Namespace object for handle_add_alias
        class Args:
            pass
        
        args = Args()
        args.add = ['/brew', 'brew'] # alias_name and command
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        user_aliases_path = os.path.join(project_root, 'config', 'user_aliases.json')
        
        handle_add_alias(args, user_aliases_path)

if __name__ == "__main__":
    main()
