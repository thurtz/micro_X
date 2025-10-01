#!/usr/bin/env python

import os
import sys
import subprocess
import argparse
import logging
import shutil
import glob
import json # Added for loading configuration

# --- Help Text ---
HELP_TEXT = """
micro_X Help: Developer & Contribution Guide

This utility manages the multi-branch development environment, allowing you to run commands across the main, testing, and dev branches.

Usage:
  /dev <option>

Environment Setup:
  --activate              - Clones and sets up the 'testing' and 'dev' branches into subdirectories.

Updating Branches:
  --update-all            - Pulls the latest changes for both the 'testing' and 'dev' branches.
  --update-testing        - Pulls the latest changes for only the 'testing' branch.
  --update-dev            - Pulls the latest changes for only the 'dev' branch.

Snapshot Generation:
  --snapshot-main [args]  - Generates a snapshot from the main branch.
  --snapshot-testing [args] - Generates a snapshot from the testing branch.
  --snapshot-dev [args]   - Generates a snapshot from the dev branch.
  --snapshot-all [args]   - Generates snapshots for all three branches.

Running Tests:
  --run-tests-main        - Runs the test suite in the main branch environment.
  --run-tests-testing     - Runs the test suite in the testing branch environment.
  --run-tests-dev         - Runs the test suite in the dev branch environment.
  --run-tests-all         - Runs the test suites for all three branches.
"""

# --- Configuration ---
TESTING_BRANCH_DIR_NAME = "micro_X-testing"
DEV_BRANCH_DIR_NAME = "micro_X-dev"
GIT_REPO_URL = "https://github.com/thurtz/micro_X.git"
DEFAULT_CONFIG_FILENAME = "default_config.json"
USER_CONFIG_FILENAME = "user_config.json"
CONFIG_DIR_NAME = "config"


# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_environment_root():
    """
    Determines the root of the multi-branch environment by traversing upwards
    from the current script's location. The root is the directory that IS the main
    branch and CONTAINS the testing and dev branch directories.
    """
    current_path = os.path.abspath(os.path.dirname(__file__))
    # Limit upward traversal to prevent infinite loops in unexpected structures
    for _ in range(5):
        # A directory is the environment root if it has its own main.py
        # and contains the testing and dev subdirectories.
        main_py_path = os.path.join(current_path, "main.py")
        testing_dir_path = os.path.join(current_path, TESTING_BRANCH_DIR_NAME)
        dev_dir_path = os.path.join(current_path, DEV_BRANCH_DIR_NAME)

        if os.path.isfile(main_py_path) and os.path.isdir(testing_dir_path) and os.path.isdir(dev_dir_path):
            return current_path

        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:  # Reached the filesystem root
            return None
        current_path = parent_path
    return None

# --- START: Added configuration loading functions ---
def merge_configs(base, override):
    """ Helper function to recursively merge dictionaries. """
    merged = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged

def load_configuration(project_root):
    """
    Loads configurations from default and user JSON files for this utility.
    """
    default_config_path = os.path.join(project_root, CONFIG_DIR_NAME, DEFAULT_CONFIG_FILENAME)
    user_config_path = os.path.join(project_root, CONFIG_DIR_NAME, USER_CONFIG_FILENAME)

    base_config = {}
    if os.path.exists(default_config_path):
        try:
            with open(default_config_path, 'r') as f:
                base_config = json.load(f)
        except Exception as e:
            print(f"❌ Error loading default configuration: {e}")
            return None # Cannot proceed without a base config
    else:
        print("❌ Error: Default configuration file not found. Cannot determine activation rules.")
        return None

    if os.path.exists(user_config_path):
        try:
            with open(user_config_path, 'r') as f:
                user_settings = json.load(f)
            return merge_configs(base_config, user_settings)
        except Exception as e:
            print(f"⚠️ Warning: Could not load or parse user config. Using defaults only. Error: {e}")
    
    return base_config
# --- END: Added configuration loading functions ---


def run_command(command, cwd, step_name, capture=False):
    """
    Runs a command, allowing it to interact directly with the terminal by default,
    and handles errors. Can optionally capture output.
    """
    logger.info(f"Running command for '{step_name}': {' '.join(command)}")
    print(f"\n--> Running: {' '.join(command)}")
    try:
        if capture:
            process = subprocess.run(
                command, cwd=cwd, check=True, capture_output=True, text=True,
                encoding='utf-8', errors='replace'
            )
            if process.stdout:
                logger.info(f"Output from '{step_name}':\n{process.stdout.strip()}")
            if process.stderr:
                logger.warning(f"Stderr from '{step_name}':\n{process.stderr.strip()}")
            print(f"--> Success: {step_name} completed.")
            return process.stdout.strip()
        else:
            subprocess.run(command, cwd=cwd, check=True, encoding='utf-8', errors='replace')
            print(f"--> Success: {step_name} completed.")
            return True
    except FileNotFoundError:
        logger.error(f"Error during '{step_name}': Command '{command[0]}' not found.")
        print(f"❌ Error: Command '{command[0]}' not found. Is it installed and in your PATH?")
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during '{step_name}' (return code {e.returncode})")
        print(f"\n❌ Error during '{step_name}'. The command failed with return code {e.returncode}.")
        if e.stdout: print(f"--- stdout ---\n{e.stdout}")
        if e.stderr: print(f"--- stderr ---\n{e.stderr}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during '{step_name}': {e}", exc_info=True)
        print(f"❌ An unexpected error occurred during '{step_name}': {e}")
        return None

def activate_dev_environment(project_root):
    """Clones and sets up the testing and dev branches."""
    print("🚀 Activating micro_X development environment...")
    print("This process will be interactive as it runs the setup scripts.")

    # --- START: Updated branch check logic ---
    print("\n[Step 1/5] Verifying current branch...")
    config = load_configuration(project_root)
    if not config:
        return # Stop if config loading failed

    allowed_branches = config.get("integrity_check", {}).get("dev_activation_allowed_branches", ["main"])

    if not shutil.which("git"):
        print("❌ Error: 'git' command not found. Please install Git and ensure it's in your PATH.")
        return

    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=project_root, capture_output=True, text=True, check=True
        )
        current_branch = result.stdout.strip()
        if current_branch not in allowed_branches:
            print(f"❌ Error: For safety, this utility can only be run from specific branches.")
            print(f"   You are currently on: '{current_branch}'")
            print(f"   Allowed branches are configured as: {', '.join(allowed_branches)}")
            print(f"   You can change this in your 'user_config.json' file if needed.")
            return
        print(f"--> Success: Currently on '{current_branch}' branch (which is allowed).")
    except Exception as e:
        print(f"❌ Error checking current branch: {e}")
        return
    # --- END: Updated branch check logic ---

    # 2. Clone Branches
    branches_to_clone = [
        ("testing", os.path.join(project_root, TESTING_BRANCH_DIR_NAME)),
        ("dev", os.path.join(project_root, DEV_BRANCH_DIR_NAME))
    ]

    print("\n[Step 2/5] Cloning development branches...")
    for branch_name, target_dir in branches_to_clone:
        print(f"\n--- Setting up '{branch_name}' branch ---")
        if os.path.isdir(target_dir):
            print(f"--> Directory '{os.path.basename(target_dir)}' already exists. Skipping clone.")
            continue

        clone_command = [
            'git', 'clone', '--branch', branch_name, GIT_REPO_URL, target_dir
        ]
        if not run_command(clone_command, project_root, f"Cloning {branch_name} branch"):
            print(f"Halting due to error cloning '{branch_name}'.")
            return

    # 3. Install Dependencies for each branch
    print("\n[Step 3/5] Installing dependencies via setup.sh...")
    for branch_name, target_dir in branches_to_clone:
        print(f"\n--- Installing for '{branch_name}' branch in '{os.path.basename(target_dir)}/' ---")
        if not os.path.isdir(target_dir):
            print(f"--> Directory '{os.path.basename(target_dir)}' not found. Skipping dependency installation.")
            continue

        setup_script_path = os.path.join(target_dir, 'setup.sh')
        if not os.path.isfile(setup_script_path):
            print(f"❌ Error: 'setup.sh' not found in '{os.path.basename(target_dir)}'. Cannot install dependencies.")
            continue

        os.chmod(setup_script_path, 0o755)
        install_command = [setup_script_path]
        if not run_command(install_command, target_dir, f"Running setup for {branch_name}"):
            print(f"Halting due to error installing dependencies for '{branch_name}'.")
            return

    # 4. Setup Development Environment Dependencies
    print("\n[Step 4/5] Setting up development tools (pytest, etc.)...")
    for branch_name, target_dir in branches_to_clone:
        print(f"\n--- Setting up dev tools for '{branch_name}' branch ---")
        if not os.path.isdir(target_dir):
            continue

        python_executable = os.path.join(target_dir, '.venv', 'bin', 'python')
        setup_dev_script = os.path.join(target_dir, 'utils', 'setup_dev_env.py')

        if not os.path.isfile(python_executable) or not os.path.isfile(setup_dev_script):
            print(f"❌ Error: Dev environment for '{branch_name}' is incomplete. Python executable or setup script missing.")
            continue

        dev_setup_command = [python_executable, setup_dev_script]
        run_command(dev_setup_command, target_dir, f"Running dev setup for {branch_name}")

    # 5. Final Summary
    print("\n[Step 5/5] Summary")
    print("✅ Development environment activation complete.")
    print(f"  - {TESTING_BRANCH_DIR_NAME}/ (testing branch)")
    print(f"  - {DEV_BRANCH_DIR_NAME}/ (dev branch)")
    print("\nYou can now use '/utils dev --update-all' or '/utils dev --snapshot-dev'.")

def update_single_branch(environment_root, branch_name, branch_dir_name):
    """Pulls the latest changes for a single specified branch installation."""
    print(f"\n--- Updating '{branch_name}' branch ---")
    target_dir = os.path.join(environment_root, branch_dir_name)
    if not os.path.isdir(target_dir):
        print(f"--> Directory '{branch_dir_name}' not found. Skipping update.")
        return
    
    pull_command = ['git', 'pull', 'origin', branch_name]
    run_command(pull_command, target_dir, f"Pulling updates for {branch_name}")

def snapshot_for_branch(environment_root, branch_name, branch_project_root_path, extra_args):
    """Generates a snapshot from a specified branch, passing along extra arguments."""
    branch_dir_name = os.path.basename(branch_project_root_path)
    print(f"📸 Generating snapshot from the '{branch_dir_name}' environment...")
    
    if not os.path.isdir(branch_project_root_path):
        print(f"❌ Error: Directory '{branch_dir_name}' not found.")
        if branch_name != 'main':
            print("   Please run '/utils dev --activate' first.")
        return

    python_executable = os.path.join(branch_project_root_path, '.venv', 'bin', 'python')
    snapshot_script = os.path.join(branch_project_root_path, 'utils', 'generate_snapshot.py')

    if not os.path.isfile(python_executable) or not os.path.isfile(snapshot_script):
        print(f"❌ Error: Environment for '{branch_dir_name}' is incomplete. Python executable or snapshot script is missing.")
        return

    snapshot_command = [python_executable, snapshot_script]
    snapshot_command.extend(extra_args)

    if not any(arg.startswith('--summary') or arg == '-s' for arg in extra_args):
        snapshot_command.extend(['--summary', f'Generated from main branch for {branch_name} branch'])
    if '--include-logs' not in extra_args:
        snapshot_command.append('--include-logs')
    
    output = run_command(snapshot_command, branch_project_root_path, f"Generating snapshot for {branch_name}", capture=True)
    if output is None:
        print("❌ Snapshot generation failed.")
        return

    created_file_path = None
    for line in output.splitlines():
        if "Successfully generated snapshot:" in line:
            created_file_path = line.split(":", 1)[1].strip()
            break
    
    if not created_file_path or not os.path.exists(created_file_path):
        print("❌ Could not determine the created snapshot filename from the script output.")
        return

    snapshot_sub_dir = os.path.join(environment_root, 'snapshots', branch_name)
    os.makedirs(snapshot_sub_dir, exist_ok=True)
    
    try:
        shutil.move(created_file_path, snapshot_sub_dir)
        final_path = os.path.join(snapshot_sub_dir, os.path.basename(created_file_path))
        print(f"\n✅ Snapshot successfully generated and moved to the main project's snapshot directory.")
        print(f"   File: {final_path}")
    except Exception as e:
        print(f"❌ Error moving snapshot file: {e}")

def run_tests_for_branch(environment_root, branch_name, branch_project_root_path):
    """Runs the test suite for a specified branch installation."""
    branch_dir_name = os.path.basename(branch_project_root_path)
    print(f"🧪 Running test suite for the '{branch_name}' environment...")
    
    if not os.path.isdir(branch_project_root_path):
        print(f"❌ Error: Directory '{branch_dir_name}' not found.")
        if branch_name != 'main':
            print("   Please run '/utils dev --activate' first.")
        return

    python_executable = os.path.join(branch_project_root_path, '.venv', 'bin', 'python')
    run_tests_script = os.path.join(branch_project_root_path, 'utils', 'run_tests.py')

    if not os.path.isfile(python_executable) or not os.path.isfile(run_tests_script):
        print(f"❌ Error: '{branch_dir_name}' environment is incomplete. Python executable or run_tests.py is missing.")
        print("   Please run './setup_main_for_dev.sh' for the main branch, or check the sub-directory setups.")
        return

    test_command = [python_executable, run_tests_script]
    
    run_command(test_command, branch_project_root_path, f"Running tests for {branch_name}")

def main():
    """Main function to parse arguments and execute logic."""
    class HelpAction(argparse.Action):
        def __init__(self, option_strings, dest, **kwargs):
            super(HelpAction, self).__init__(option_strings, dest, nargs=0, **kwargs)
        def __call__(self, parser, namespace, values, option_string=None):
            print(HELP_TEXT)
            parser.exit()

    parser = argparse.ArgumentParser(
        description="Manage the micro_X multi-branch development environment.",
        add_help=False
    )
    parser.add_argument('-h', '--help', action=HelpAction, help='show this help message and exit')

    # --- Group for exclusive actions ---
    action_group = parser.add_mutually_exclusive_group(required=False)
    action_group.add_argument(
        "--activate", action="store_true",
        help="Clones and sets up the 'testing' and 'dev' branches into subdirectories."
    )
    action_group.add_argument(
        "--update-all", action="store_true",
        help="Pulls the latest changes for both the 'testing' and 'dev' branch installations."
    )
    action_group.add_argument(
        "--update-testing", action="store_true",
        help="Pulls the latest changes for only the 'testing' branch installation."
    )
    action_group.add_argument(
        "--update-dev", action="store_true",
        help="Pulls the latest changes for only the 'dev' branch installation."
    )
    action_group.add_argument(
        "--snapshot-main", nargs=argparse.REMAINDER,
        help="Generates a snapshot from the main branch. All following arguments are passed to generate_snapshot.py."
    )
    action_group.add_argument(
        "--snapshot-testing", nargs=argparse.REMAINDER,
        help="Generates a snapshot from the testing branch. All following arguments are passed to generate_snapshot.py."
    )
    action_group.add_argument(
        "--snapshot-dev", nargs=argparse.REMAINDER,
        help="Generates a snapshot from the dev branch. All following arguments are passed to generate_snapshot.py."
    )
    action_group.add_argument(
        "--snapshot-all", nargs=argparse.REMAINDER,
        help="Generates snapshots for main, testing, and dev branches. Following arguments are passed to all."
    )
    action_group.add_argument(
        "--run-tests-main", action="store_true",
        help="Runs the test suite located in the main branch environment."
    )
    action_group.add_argument(
        "--run-tests-dev", action="store_true",
        help="Runs the test suite located in the dev branch environment."
    )
    action_group.add_argument(
        "--run-tests-testing", action="store_true",
        help="Runs the test suite located in the testing branch environment."
    )
    action_group.add_argument(
        "--run-tests-all", action="store_true",
        help="Runs the test suites for the main, testing, and dev branches."
    )

    # If no arguments are provided, print help text
    if len(sys.argv) == 1:
        print(HELP_TEXT)
        sys.exit(0)

    args = parser.parse_args()
    
    environment_root = find_environment_root()
    if environment_root is None:
        # Fallback for when the script is run from a non-activated environment
        # This allows --activate to still work
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if args.activate:
             activate_dev_environment(project_root)
             return
        print("❌ Error: Could not find the micro_X multi-branch environment root.")
        print("   Ensure you are running this from within an activated environment, or run '/dev --activate' from the main branch.")
        sys.exit(1)

    # Get the name of the main branch directory, which might be different from the env root basename
    main_branch_dir = os.path.join(environment_root)

    # Execute the chosen action
    if args.activate:
        # The activate command should be run from the main branch directory
        activate_dev_environment(main_branch_dir)
    elif args.update_all:
        print("🔄 Updating all development environment branches...")
        update_single_branch(environment_root, "testing", TESTING_BRANCH_DIR_NAME)
        update_single_branch(environment_root, "dev", DEV_BRANCH_DIR_NAME)
        print("\n✅ All development branches have been updated.")
    elif args.update_testing:
        update_single_branch(environment_root, "testing", TESTING_BRANCH_DIR_NAME)
    elif args.update_dev:
        update_single_branch(environment_root, "dev", DEV_BRANCH_DIR_NAME)
    elif args.snapshot_main is not None:
        snapshot_for_branch(environment_root, "main", main_branch_dir, args.snapshot_main)
    elif args.snapshot_testing is not None:
        snapshot_for_branch(environment_root, "testing", os.path.join(environment_root, TESTING_BRANCH_DIR_NAME), args.snapshot_testing)
    elif args.snapshot_dev is not None:
        snapshot_for_branch(environment_root, "dev", os.path.join(environment_root, DEV_BRANCH_DIR_NAME), args.snapshot_dev)
    elif args.snapshot_all is not None:
        print("📸 Generating snapshots for all branches...")
        snapshot_for_branch(environment_root, "main", main_branch_dir, args.snapshot_all)
        snapshot_for_branch(environment_root, "testing", os.path.join(environment_root, TESTING_BRANCH_DIR_NAME), args.snapshot_all)
        snapshot_for_branch(environment_root, "dev", os.path.join(environment_root, DEV_BRANCH_DIR_NAME), args.snapshot_all)
        print("\n✅ All snapshots generated.")
    elif args.run_tests_main:
        run_tests_for_branch(environment_root, "main", main_branch_dir)
    elif args.run_tests_dev:
        run_tests_for_branch(environment_root, "dev", os.path.join(environment_root, DEV_BRANCH_DIR_NAME))
    elif args.run_tests_testing:
        run_tests_for_branch(environment_root, "testing", os.path.join(environment_root, TESTING_BRANCH_DIR_NAME))
    elif args.run_tests_all:
        print("🧪 Running test suites for all branches...")
        run_tests_for_branch(environment_root, "main", main_branch_dir)
        run_tests_for_branch(environment_root, "testing", os.path.join(environment_root, TESTING_BRANCH_DIR_NAME))
        run_tests_for_branch(environment_root, "dev", os.path.join(environment_root, DEV_BRANCH_DIR_NAME))
        print("\n✅ All test suites have been run.")

if __name__ == "__main__":
    main()