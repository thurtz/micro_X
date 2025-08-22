#!/usr/bin/env python

import os
import sys
import subprocess
import hashlib
import logging
import shutil

# --- Configuration ---
REQUIREMENTS_FILENAME = "requirements.txt"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def get_project_root():
    """
    Determines the project root directory. Assumes this script is in a 'utils'
    subdirectory of the project root.
    """
    script_path = os.path.abspath(__file__)
    utils_dir = os.path.dirname(script_path)
    project_root = os.path.dirname(utils_dir)

    # A simple sanity check to ensure we're in the right place
    if os.path.exists(os.path.join(project_root, "main.py")) or os.path.exists(os.path.join(project_root, ".git")):
        return project_root
    else:
        # Fallback if the structure is unexpected
        logger.warning(f"Could not reliably determine project root from script location: {script_path}. Using parent directory.")
        return project_root

def get_file_hash(filepath):
    """Calculates the SHA256 hash of a file's content."""
    if not os.path.exists(filepath):
        return None
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Error hashing file {filepath}: {e}", exc_info=True)
        return None

def run_update():
    """
    Handles the main logic for updating the application by pulling changes from git.
    This function prints directly to stdout for consumption by the ShellEngine.
    """
    print("🔄 Checking for updates...")
    logger.info("Update utility started.")

    project_root = get_project_root()
    requirements_path = os.path.join(project_root, REQUIREMENTS_FILENAME)

    if not shutil.which("git"):
        print("❌ Update failed: 'git' command not found in your system's PATH.")
        logger.error("Update failed: git command not found.")
        return

    original_req_hash = get_file_hash(requirements_path)

    try:
        # 1. Get the current branch name
        branch_process = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=project_root, capture_output=True, text=True, check=True, errors='replace'
        )
        current_branch = branch_process.stdout.strip()
        print(f"ℹ️ On branch: '{current_branch}'. Fetching updates from 'origin/{current_branch}'...")
        logger.info(f"Current git branch: {current_branch}")

        # 2. Run 'git pull'
        pull_process = subprocess.run(
            ['git', 'pull', 'origin', current_branch],
            cwd=project_root, capture_output=True, text=True, errors='replace'
        )

        # 3. Process the result
        if pull_process.returncode == 0:
            print(f"✅ Git pull successful.\n--- Git Output ---\n{pull_process.stdout.strip()}\n------------------")
            logger.info(f"Git pull output: {pull_process.stdout.strip()}")

            if "Already up to date." in pull_process.stdout:
                print("✅ micro_X is already up to date.")
            else:
                print("✅ Updates were downloaded.")
                new_req_hash = get_file_hash(requirements_path)
                if original_req_hash != new_req_hash:
                    print(f"⚠️ {REQUIREMENTS_FILENAME} has changed.")
                    logger.info(f"{REQUIREMENTS_FILENAME} changed during update.")
                    print("💡 After restarting, consider updating dependencies by running:")
                    print(f"   /utils install_requirements --all")
                print("💡 Please restart micro_X for the changes to take effect.")
        else:
            print(f"❌ Git pull failed.\n--- Git Error ---\n{pull_process.stderr.strip()}\n-----------------")
            logger.error(f"Git pull failed. Stderr: {pull_process.stderr.strip()}")

    except subprocess.CalledProcessError as e:
        error_message = e.stderr.strip() if e.stderr else str(e)
        print(f"❌ Update failed: A git command failed.\n--- Error ---\n{error_message}\n-------------")
        logger.error(f"Update git error: {e}", exc_info=True)
    except FileNotFoundError:
        print("❌ Update failed: 'git' command not found (unexpected).")
        logger.error("Update failed: git not found during execution.")
    except Exception as e:
        print(f"❌ An unexpected error occurred during the update process: {e}")
        logger.error(f"Unexpected update error: {e}", exc_info=True)

if __name__ == "__main__":
    run_update()
